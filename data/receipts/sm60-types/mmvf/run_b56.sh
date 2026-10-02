#!/usr/bin/env bash
# PREREG_MMVF_SHORTROW.md B5/B6 (Deviation 3 run plan), driven from the desktop against .194. Resumable per step.
#   B5: four fresh servers, ABBA (base, final, final, base); gates; embedding shard pre-read; G0; warm-up; hc_probe.py
#   B6: llama-perplexity -ub 1: base logits, base-vs-base self-control, final-vs-base
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; SM="$HERE/.."; VIA="$HERE/../../viability"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"
RHOME=$(ssh "$H" 'echo $HOME'); W="$RHOME/mmvf"; M="$RHOME/AI/Models/fn_gsq_base"
S1="$M/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf"
S2="$M/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf"
FLAGS="-ngl 99 -sm layer -ts 1,1,1,0.6 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off --host 0.0.0.0 --port $PORT"
ENVS="CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal"
OUT="$HERE/raw_b56"; mkdir -p "$OUT"; LOG="$OUT/run.log"; DEC="$OUT/decode.jsonl"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
stop_server() {
  ssh "$H" 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' \
    || { log "a llama-server survived pkill -- aborting"; exit 1; }
}
trap stop_server EXIT
ssh "$H" 'test -x ~/mmvf/base/llama-server && test -x ~/mmvf/final/llama-server && grep -q BUILD_OK ~/mmvf/build.log' \
  || { log "builds not ready"; exit 1; }
log "== b56 start; cfg: $(ssh "$H" 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" ";"')"
log "binaries: $(ssh "$H" 'cd ~/mmvf && sha256sum base/* final/* | cut -c1-16 | tr "\n" " "')"

# ---- B5 decode
rows() { [ -f "$DEC" ] && $PY -c 'import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l)["arm"]==sys.argv[2]))' "$DEC" "$1" || echo 0; }
for tag in base_s1 final_s1 final_s2 base_s2; do
  build=${tag%_*}
  [ "$(rows "$tag")" -ge 12 ] && { log "$tag done, skipped"; continue; }
  [ "$(rows "$tag")" -gt 0 ] && { log "$tag has a partial set -- refusing to mix; move it aside"; exit 1; }
  stop_server
  ssh "$H" "$ENVS nohup $W/$build/llama-server -m $S1 $FLAGS > $W/srv_$tag.log 2>&1 < /dev/null &"
  up=0
  for i in $(seq 1 120); do
    sleep 5
    ssh "$H" 'pgrep -x llama-server >/dev/null' || { log "$tag: server died: $(ssh "$H" "tail -3 $W/srv_$tag.log")"; exit 1; }
    curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }
  done
  [ $up = 1 ] || { log "$tag: not healthy after 600 s"; exit 1; }
  mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$mp" = "$S1" ] || { log "$tag: WRONG MODEL: $mp"; exit 1; }
  exe=$(ssh "$H" 'readlink /proc/$(pgrep -x llama-server)/exe')
  [ "$exe" = "$W/$build/llama-server" ] || { log "$tag: WRONG BINARY: $exe"; exit 1; }
  ssh "$H" "grep -q 'offloaded 49/49 layers to GPU' $W/srv_$tag.log" || { log "$tag: placement not 49/49"; exit 1; }
  t0=$(date +%s); ssh "$H" "cat $S2 > /dev/null"; log "$tag: verified ($exe, 49/49); shard 2 pre-read $(( $(date +%s) - t0 )) s"
  $PY "$VIA/swift_fn_probe.py" gate "$URL" >> "$LOG" 2>&1 || { log "$tag: G0 coherence FAIL"; exit 1; }
  curl -s -m 600 "$URL/v1/chat/completions" -H 'content-type: application/json' \
    -d '{"messages":[{"role":"user","content":"Say ready."}],"max_tokens":8,"cache_prompt":false,"chat_template_kwargs":{"enable_thinking":false}}' >/dev/null
  log "$tag: decode probe"
  (cd "$SM" && $PY hc_probe.py "$URL" "$tag" "$DEC") >> "$LOG" 2>&1
  log "$tag: $(rows "$tag") rows; clocks $(ssh "$H" 'nvidia-smi --query-gpu=clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" " "')"
done
stop_server
scp -q "$H:mmvf/srv_*.log" "$OUT/" 2>/dev/null

# ---- B6 fidelity at -ub 1
PF="-ngl 99 -sm layer -ts 1,1,1,0.6 -fit off -c 512 -b 512 -ub 1 -ctk f16 -ctv f16 -lv 4 --chunks 16 -f $RHOME/wikitext-2-raw/wiki.test.raw"
ppl() {  # name build extra-args
  local name=$1 build=$2; shift 2
  [ -s "$OUT/$name.txt" ] && grep -q 'prompt eval time' "$OUT/$name.txt" && { log "$name done, skipped"; return 0; }
  ssh "$H" "cat $S2 > /dev/null"
  local t0=$(date +%s)
  ssh "$H" "$ENVS $W/$build/llama-perplexity -m $S1 $PF $*" > "$OUT/$name.txt" 2>&1
  grep -q 'VBR dynamic' "$OUT/$name.txt" && { log "$name: VBR KV active -- aborting"; exit 1; }
  log "$name: exit $? in $(( $(date +%s) - t0 )) s; $(grep -E 'Mean +KLD|Final estimate' "$OUT/$name.txt" | head -1); $(grep -o 'prompt eval time = .*' "$OUT/$name.txt" | head -1)"
}
ppl kld_base base --kl-divergence-base $W/kld_base.bin
ppl kld_self base --kl-divergence-base $W/kld_base.bin --kl-divergence
ppl kld_final final --kl-divergence-base $W/kld_base.bin --kl-divergence
log "== b56 done"
