#!/usr/bin/env bash
# PREREG_SM60_TYPES.md. Part 1: test-backend-ops perf (MUL_MAT all, MUL_MAT_ID n_mats=512) on GPU 0 of .194 in clock
# blocks E P P E E P. Part 2: decode probe for UD-Q2_K_XL and GSQ-RCO base on fresh verified servers, blocks E P E.
# The efficiency config (150 W / 1063) is ALWAYS restored on exit and read back. Resumable per perf block / decode cell.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; VIA="$HERE/../viability"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"
BIN='~/buun-0b278/build_sm60/bin/llama-server'; TBO='~/test-backend-ops-fn'
declare -A MODEL=([UDQ2]='~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf'
                  [GSQB]='~/AI/Models/fn_gsq_base/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf')
FLAGS="-ngl 99 -sm layer -ts 1,1,1,0.6 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0 --port $PORT"
declare -A CFG=([E]="sudo nvidia-smi -pl 150 >/dev/null && sudo nvidia-smi -ac 715,1063 >/dev/null"
                [P]="sudo nvidia-smi -pl 150 >/dev/null && sudo nvidia-smi -ac 715,1328 >/dev/null")
OUT="$HERE/raw"; mkdir -p "$OUT"; LOG="$OUT/run.log"; DEC="$OUT/decode.jsonl"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
stop_server() {
  ssh "$H" 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' \
    || { log "a llama-server survived pkill -- aborting"; exit 1; }
}
restore() {
  stop_server
  ssh "$H" 'sudo systemctl restart p100-efficiency' && log "restored: $(ssh "$H" 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" ";"')"
  scp -q "$H:sm60_*.log" "$OUT/" 2>/dev/null
}
trap restore EXIT
set_cfg() { ssh "$H" "${CFG[$1]}"; sleep 5; ssh "$H" 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" ";"'; }

log "== sm60-types start"
ssh "$H" 'pgrep -x llama-server >/dev/null' && stop_server
# ---- part 1: kernels
b=0
for c in E P P E E P; do
  f="$OUT/perf_${c}_b$b.txt"
  if [ -s "$f" ] && [ "$(grep -c 'us/run' "$f")" -ge 150 ]; then log "perf block $b ($c) done, skipped"; b=$((b+1)); continue; fi
  log "perf block $b cfg $c: $(set_cfg "$c")"
  ssh "$H" "CUDA_VISIBLE_DEVICES=0 $TBO perf -o MUL_MAT -b CUDA0; CUDA_VISIBLE_DEVICES=0 $TBO perf -o MUL_MAT_ID -b CUDA0 -p n_mats=512" > "$f" 2>&1
  log "perf block $b exit $? ($(grep -c 'us/run' "$f") timed cases)"
  b=$((b+1))
done
# ---- part 2: decode
have() { [ -f "$DEC" ] && [ "$($PY -c 'import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l)["arm"]==sys.argv[2]))' "$DEC" "$1")" -ge 12 ]; }
for fk in UDQ2 GSQB; do
  model=${MODEL[$fk]}
  have "${fk}_E1" && have "${fk}_P1" && have "${fk}_E2" && { log "$fk decode done, skipped"; continue; }
  set_cfg E >/dev/null
  stop_server
  ssh "$H" "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $model $FLAGS > ~/sm60_$fk.log 2>&1 < /dev/null &"
  up=0
  for i in $(seq 1 120); do
    sleep 5
    ssh "$H" 'pgrep -x llama-server >/dev/null' || { log "$fk: server died: $(ssh "$H" "tail -3 ~/sm60_$fk.log")"; exit 1; }
    ssh "$H" "grep -q 'model loaded' ~/sm60_$fk.log" && curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }
  done
  [ $up = 1 ] || { log "$fk: not healthy after 600 s"; exit 1; }
  mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$model")" ] || { log "$fk: WRONG SERVER: $mp"; exit 1; }
  ssh "$H" "grep -q 'offloaded 49/49 layers to GPU' ~/sm60_$fk.log" || { log "$fk: placement not 49/49"; exit 1; }
  log "$fk: verified -- 49/49 on GPU, $(basename "$mp"), pid $(ssh "$H" 'pgrep -x llama-server')"
  curl -s -m 600 "$URL/v1/chat/completions" -H 'content-type: application/json' \
    -d '{"messages":[{"role":"user","content":"Say ready."}],"max_tokens":8,"cache_prompt":false,"chat_template_kwargs":{"enable_thinking":false}}' >/dev/null
  for cell in E1 P1 E2; do
    have "${fk}_$cell" && continue
    log "$fk decode $cell: $(set_cfg "${cell:0:1}")"
    $PY "$VIA/swift_fn_probe.py" speed "$URL" "${fk}_$cell" off "$DEC" >> "$LOG" 2>&1
  done
done
log "== sm60-types done"
