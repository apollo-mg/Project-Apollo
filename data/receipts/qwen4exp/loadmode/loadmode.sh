#!/usr/bin/env bash
# JOB A: does -lm none / dio beat mmap for a model whose working set exceeds RAM?
# llama.cpp has been printing "tensor overrides to CPU are used with mmap enabled - consider using
# --load-mode none for better performance" on every Flash-Next load and we ignored it twice.
# This also supplies PREREG_DIMM_UPGRADE.md P-D7's pre-upgrade baseline under the dropped-cache
# protocol the amendment requires -- the earlier 10m53s was incidental, not controlled.
#
# If a flag fixes cold-load time, P-D7 (which credits the DIMM upgrade for it) is CONFOUNDED and
# must be rewritten before the sticks arrive. That is the point of running it now.
set -u
W=~/loadmode; mkdir -p "$W"; L=$W/run.log
BIN=~/buun-c7f114d34/build_sm60/bin/llama-server
IQ4=~/AI/Models/flashnext/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf
PORT=8117
say () { echo "$(date '+%F %T') $*" | tee -a "$L"; }
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server running"; exit 1; }

for MODE in auto none dio; do
  say "=== load-mode $MODE : dropping caches"
  sudo -n sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null || say "    WARN: could not drop caches"
  sleep 3
  T0=$(date +%s)
  GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=0,1,2,3 \
    "$BIN" -m "$IQ4" -ngl 99 -ncmoe 2 --numa distribute -c 8192 -np 1 -fa on \
           -ctk f16 -ctv f16 -sm layer -fit off -lm "$MODE" \
           --host 127.0.0.1 --port $PORT > "$W/s_$MODE.log" 2>&1 &
  PID=$!
  OK=0
  for i in $(seq 1 1200); do
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { OK=1; break; }
    kill -0 "$PID" 2>/dev/null || break
    sleep 2
  done
  T1=$(date +%s)
  if [ "$OK" = 1 ]; then
    MF=$(ps -o maj_flt= -p "$PID" | tr -d ' ')
    RB=$(awk '/read_bytes/{printf "%.1f", $2/1073741824}' /proc/$PID/io 2>/dev/null)
    say "    LOADED in $((T1-T0))s | major faults $MF | read ${RB} GB | VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' '/')"
    echo "{\"mode\":\"$MODE\",\"load_s\":$((T1-T0)),\"maj_flt\":$MF,\"read_gb\":$RB}" >> "$W/rows.jsonl"
  else
    say "    FAILED after $((T1-T0))s"
    tail -4 "$W/s_$MODE.log" | sed 's/^/    /' | tee -a "$L"
    echo "{\"mode\":\"$MODE\",\"load_s\":null}" >> "$W/rows.jsonl"
  fi
  kill "$PID" 2>/dev/null; wait "$PID" 2>/dev/null
  for i in $(seq 1 150); do
    [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ] && break
    sleep 1
  done
done
say "=== LOADMODE COMPLETE ==="
