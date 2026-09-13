#!/usr/bin/env bash
# Amendment 5 (fixed 18:35: `grep -c` prints 0 AND exits 1, so `|| echo 0` made a two-line
# value and every -gt test threw 'integer expression expected'; count with `grep -E … | wc -l`): after test 11 finishes, reload each arm's exact command with -lv 4, load only, and record the
# K/V cache types the run itself could not prove. Waits correctly whether armed before or after the run.
set -u
W=~/test11; L=$W/kvcheck.log
BIN=~/buun-c7f114d34/build_sm60/bin/llama-server
EXL3=~/AI/Models/exl3/Qwen3.8-27B-exl3-3.00bpw
GGUF=~/AI/Models/qwen27b/Qwen3.8-27B-UD-IQ3_XXS.gguf
BASE="-c 8192 -np 1 -fa on -ctk f16 -ctv f16 -sm layer -ngl 99 -fit off --jinja --chat-template-file $EXL3/chat_template.jinja --host 127.0.0.1 --port 8103 -lv 4"
say () { echo "$(date '+%F %T') $*" >> "$L"; }
markers () { grep -E "TEST 11 COMPLETE|ABORT" "$W/driver.log" 2>/dev/null | wc -l; }
N0=$(markers)
# Two modes, because the baseline-count idiom is only correct when armed BEFORE the run:
#   armed early (N0 = 0) -> wait for the count to rise, so a stale marker cannot fire the waiter;
#   run post-hoc (N0 > 0) -> the run this checks has already finished; proceed on the marker present.
if [ "${N0:-0}" -gt 0 ]; then
  say "kv-check up (pid $$), post-hoc: $N0 marker(s) already present -- $(grep -E 'TEST 11 COMPLETE|ABORT' "$W/driver.log" | tail -1)"
else
  say "kv-check up (pid $$), armed before completion, baseline markers 0"
  for i in $(seq 1 240); do
    [ "$(markers)" -gt "$N0" ] && break
    sleep 30
  done
  [ "$(markers)" -gt "$N0" ] || { say "gave up waiting for test 11"; exit 1; }
fi
for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || break; sleep 10; done
pgrep -x llama-server >/dev/null && { say "ABORT: a server is still running"; exit 1; }
check () {   # arm model gpus node
  local arm=$1 model=$2 gpus=$3 node=$4 log=$W/kvload_$1.log
  GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=$gpus \
    numactl --cpunodebind=$node --membind=$node "$BIN" -m "$model" $BASE > "$log" 2>&1 &
  local pid=$!
  for i in $(seq 1 900); do
    curl -sf http://127.0.0.1:8103/health >/dev/null 2>&1 && break
    kill -0 "$pid" 2>/dev/null || break
    sleep 2
  done
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  say "$arm: KV $(grep -oE '\b[KV] \([A-Za-z0-9_]+\)' "$log" | sort -u | tr '\n' ' ')| $(grep -c 'model buffer size' "$log") buffer lines | $(grep -oE 'offloaded [0-9]+/[0-9]+ layers' "$log" | head -1)"
  for i in $(seq 1 90); do [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ] && break; sleep 1; done
}
check exl3 "$EXL3" 0,1 0
check gguf "$GGUF" 2,3 1
say "=== KV CHECK COMPLETE ==="
