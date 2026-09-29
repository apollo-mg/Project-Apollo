#!/usr/bin/env bash
# PREREG_HC_Q8.md. Runs only after run_sm60_types.sh has finished. Steps (each resumable):
#   1 build: a second patched test-backend-ops (fn_hc_cases.inc) -> ~/test-backend-ops-hc, tree restored; llama-perplexity
#   2 kernel control: perf at E, 3 reps, the hc shapes in F16/F32/BF16/Q8_0
#   3 retype: shard 1 of the GSQ base, hc_* BF16 -> Q8_0, --verify; shard 2 symlinked
#   4 decode: HCQ8 then GSQB, fresh verified servers (FULL path checked), G0 coherence, warm-up, hc_probe.py
#   5 fidelity: llama-perplexity KLD, HCQ8 against GSQB logits, wikitext-2 test, 16 x 512
# The efficiency config is restored and read back on exit.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; VIA="$HERE/../viability"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"
B='~/buun-0b278'; BIN="$B/build_sm60/bin/llama-server"; PPL="$B/build_sm60/bin/llama-perplexity"
RHOME=$(ssh "$H" 'echo $HOME'); M="$RHOME/AI/Models"      # absolute on .194, so /props can be compared exactly
SRC1="$M/fn_gsq_base/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf"
SRC2="$M/fn_gsq_base/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"
HCQ="$M/fn_gsq_base_hcq8/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf"
FLAGS="-ngl 99 -sm layer -ts 1,1,1,0.6 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0 --port $PORT"
OUT="$HERE/raw_hc"; mkdir -p "$OUT"; LOG="$OUT/run.log"; DEC="$OUT/decode.jsonl"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
stop_server() {
  ssh "$H" 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' \
    || { log "a llama-server survived pkill -- aborting"; exit 1; }
}
restore() {
  stop_server
  ssh "$H" 'sudo systemctl restart p100-efficiency' && log "restored: $(ssh "$H" 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" ";"')"
  scp -q "$H:hcq8_*.log" "$OUT/" 2>/dev/null
}
trap restore EXIT

grep -q '== sm60-types done' "$HERE/raw/run.log" || { echo "kernel run not finished"; exit 1; }
log "== hc-q8 start"
ssh "$H" 'sudo nvidia-smi -pl 150 >/dev/null && sudo nvidia-smi -ac 715,1063 >/dev/null'
log "cfg: $(ssh "$H" 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" ";"')"

# ---- 1 build
if ! ssh "$H" 'test -x ~/test-backend-ops-hc && test -x ~/buun-0b278/build_sm60/bin/llama-perplexity'; then
  scp -q "$HERE/fn_hc_cases.inc" "$HERE/hc_build.sh" "$H:/tmp/"
  ssh "$H" 'bash /tmp/hc_build.sh' >> "$LOG" 2>&1 && grep -q BUILD_OK "$LOG" || { log "build failed"; exit 1; }
  log "built test-backend-ops-hc and llama-perplexity"
fi
# ---- 2 kernel control
for rep in 1 2 3; do
  f="$OUT/perf_hc_E_r$rep.txt"
  [ -s "$f" ] && [ "$(grep -c 'us/run' "$f")" -ge 8 ] && continue
  ssh "$H" "CUDA_VISIBLE_DEVICES=0 ~/test-backend-ops-hc perf -o MUL_MAT -b CUDA0 -p 'type_a=(f16|f32|bf16|q8_0),type_b=f32,m=(10240|320),n=1,k=(320|10240),'" > "$f" 2>&1
  log "kernel control rep $rep: $(grep -c 'us/run' "$f") timed cases"
done
# ---- 3 retype
if ! ssh "$H" "test -s $HCQ && test -L $M/fn_gsq_base_hcq8/$(basename "$SRC2")"; then
  scp -q /mnt/TG_2TB/Projects/Apollo/tools/gguf_retype.py "$H:/tmp/gguf_retype.py"
  ssh "$H" "mkdir -p $M/fn_gsq_base_hcq8 && cd $M/fn_gsq_base_hcq8 && python3 /tmp/gguf_retype.py $SRC1 $HCQ.part 'hc_(attn|ffn)_(up|down)\.weight' --verify && mv $HCQ.part $HCQ && ln -sf $SRC2 ." >> "$LOG" 2>&1 \
    || { log "retype FAILED"; exit 1; }
  log "retype done: $(ssh "$H" "ls -laL $M/fn_gsq_base_hcq8/ | tail -2 | awk '{print \$5, \$9}' | tr '\n' ' '; sha256sum $HCQ | cut -c1-16")"
fi
# ---- 4 decode
have() { [ -f "$DEC" ] && [ "$($PY -c 'import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l)["arm"]==sys.argv[2]))' "$DEC" "$1")" -ge 12 ]; }
for spec in "HCQ8|$HCQ" "GSQB|$SRC1"; do
  IFS='|' read -r arm model <<< "$spec"
  have "$arm" && { log "$arm decode done, skipped"; continue; }
  stop_server
  ssh "$H" "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $model $FLAGS > ~/hcq8_$arm.log 2>&1 < /dev/null &"
  up=0
  for i in $(seq 1 120); do
    sleep 5
    ssh "$H" 'pgrep -x llama-server >/dev/null' || { log "$arm: server died: $(ssh "$H" "tail -3 ~/hcq8_$arm.log")"; exit 1; }
    ssh "$H" "grep -q 'model loaded' ~/hcq8_$arm.log" && curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }
  done
  [ $up = 1 ] || { log "$arm: not healthy after 600 s"; exit 1; }
  mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$mp" = "$model" ] || { log "$arm: WRONG SERVER: $mp (want $model)"; exit 1; }
  ssh "$H" "grep -q 'offloaded 49/49 layers to GPU' ~/hcq8_$arm.log" || { log "$arm: placement not 49/49"; exit 1; }
  log "$arm: verified -- 49/49, $mp, types: $(ssh "$H" "grep -E 'type +(bf16|q8_0):' ~/hcq8_$arm.log | sed 's/.*- type/type/' | tr '\n' ' '")"
  $PY "$VIA/swift_fn_probe.py" gate "$URL" >> "$LOG" 2>&1 || { log "$arm: G0 coherence FAIL"; exit 1; }
  curl -s -m 600 "$URL/v1/chat/completions" -H 'content-type: application/json' \
    -d '{"messages":[{"role":"user","content":"Say ready."}],"max_tokens":8,"cache_prompt":false,"chat_template_kwargs":{"enable_thinking":false}}' >/dev/null
  log "$arm: decode probe"
  $PY "$HERE/hc_probe.py" "$URL" "$arm" "$DEC" >> "$LOG" 2>&1
done
stop_server
# ---- 5 fidelity
if [ ! -s "$OUT/kld_hcq8.txt" ]; then
  PF="-ngl 99 -sm layer -ts 1,1,1,0.6 -fit off -c 512 --chunks 16 -f ~/wikitext-2-raw/wiki.test.raw"
  ssh "$H" "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal $PPL -m $SRC1 $PF --kl-divergence-base ~/hcq8_kld_base.bin" > "$OUT/kld_base.txt" 2>&1
  log "kld base: exit $? $(grep -E 'Final estimate|PPL' "$OUT/kld_base.txt" | tail -1)"
  ssh "$H" "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal $PPL -m $HCQ $PF --kl-divergence-base ~/hcq8_kld_base.bin --kl-divergence" > "$OUT/kld_hcq8.txt" 2>&1
  log "kld hcq8: exit $? $(grep -E 'Mean +KLD' "$OUT/kld_hcq8.txt" | head -1)"
fi
log "== hc-q8 done"
