#!/usr/bin/env bash
# Runs Stage 3 of PREREG_FLASHNEXT_RESIDENCY.md (Amendment 3) on .194 once Stage 2 has finished either way, then
# the load-only -lv 4 reloads Amendment 3 promises for F-X3, the S3-X4 arm that ran, and S3-FIT. Launched detached.
set -u
R=~/flashnext_res; L=$R/stage3_launcher.log
BIN=~/buun-c7f114d34/build_sm60/bin/llama-server
M=~/AI/Models
IQ4=$M/flashnext/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf
EXL3=$M/exl3/Qwen3.8-Flash-Next-exl3-3.05bpw_h5_ng5
BASE="-c 4096 -np 1 -b 2048 -ub 512 -fa on --jinja -sm layer -ctk f16 -ctv f16 --host 127.0.0.1 --port 8094 -lv 4"
export GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=0,1,2,3
say () { echo "$(date '+%F %T') $*" >> "$L"; }
busy () { ps -eo args | grep -q "[f]lashnext_residency.py" || pgrep -x llama-server >/dev/null; }

say "stage-3 launcher up (pid $$), waiting for Stage 2 to finish either way"
for i in $(seq 1 360); do
  grep -qE "STAGE 2 COMPLETE|ABORT" "$R/driver.log" 2>/dev/null && break
  sleep 30
done
grep -qE "STAGE 2 COMPLETE|ABORT" "$R/driver.log" || { say "gave up: Stage 2 did not finish within 3 h"; exit 1; }
say "stage 2 finished: $(grep -hE 'STAGE 2 COMPLETE|ABORT' "$R/driver.log" | tail -1)"
for i in $(seq 1 60); do busy || break; sleep 10; done
busy && { say "ABORT: a driver or server is still running"; exit 1; }
sleep 20
cd "$R" && python3 -u flashnext_residency.py --stage3 >> "$R/driver.out" 2>&1
say "stage 3 driver exited rc=$?"

gpus_clear () { for i in $(seq 1 90); do [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ] && return 0; sleep 1; done; return 1; }
check () {   # label model flags...   (load only: no requests, no timing)
  local label=$1 model=$2; shift 2
  local log="$R/verify/load_$label.log"
  [ -e "$model" ] || { say "$label: $model missing -- skipped"; return; }
  "$BIN" -m "$model" $BASE "$@" > "$log" 2>&1 &
  local pid=$!
  for i in $(seq 1 1800); do
    curl -sf http://127.0.0.1:8094/health >/dev/null 2>&1 && break
    kill -0 "$pid" 2>/dev/null || break
    sleep 2
  done
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  say "$label: $(grep -oE 'offloaded [0-9]+/[0-9]+ layers' "$log" | head -1) | $(grep -c 'model buffer size' "$log") buffer lines | KV: $(grep -oE '\b[KV] \([A-Za-z0-9_]+\)' "$log" | sort -u | tr '\n' ' ')"
  gpus_clear || say "WARN: GPUs did not clear after $label"
}
mkdir -p "$R/verify"
if grep -q '"arm": "S3-X4n4"' "$R/results.jsonl"; then X4=( S3-X4n4 -fit off -ngl 99 -ncmoe 4 ); else X4=( S3-X4 -fit off -ngl 99 -ncmoe 2 ); fi
check F-X3 "$EXL3" -fit off -ngl 99
check "${X4[0]}" "$IQ4" "${X4[@]:1}"
check S3-FIT "$IQ4" -fit on -ngl 99
say "=== STAGE 3 LAUNCHER COMPLETE ==="
