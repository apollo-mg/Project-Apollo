#!/usr/bin/env bash
# Bit-depth isolation on the agentic corpus. MTP OFF both arms (VBR > MTP priority).
set -u
# FALSIFIED 2026-09-09: this is a NO-OP for this path. cli.py:2670 does read it, but
# hermesbench drives run_agent.py, which constructs AIAgent WITHOUT max_tokens (run_agent.py:1477),
# so agent.max_tokens stays None and the agent omits max_tokens either way -- verified on the wire
# with a capture stub (9/9 requests, var set and unset). The continuation ladder is hard-anchored
# to `(agent.max_tokens or 4096)` = 4096 and cannot be configured from here.
# See data/receipts/viability/RESULT_V5_TIMEOUT_BY_CONSTRUCTION.md
export HERMES_MAX_TOKENS=4096
B=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin/llama-server
BENCH=/home/mark/projects/hermes-bench-tool-call
# AFM-36: killing `hermesbench run` does NOT kill the run_agent.py it spawned. An orphan
# keeps generating and, with -np 1, starves the next run into 100% timeouts. Kill by PID.
reap_orphans(){
  for p in $(ps -eo pid,args --no-headers | awk '/run_agent\.py/ && !/awk/ {print $1}'); do
    echo "  reaping orphaned agent $p"; kill -9 $p 2>/dev/null
  done
  sleep 2
}

arm(){
  local tag="$1"; local model="$2"
  local LOG=$HOME/bd_${tag}_server.log
  reap_orphans
  pkill -x llama-server 2>/dev/null
  for i in $(seq 1 24); do
    u=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -i 'Total Used' | grep -oE '[0-9]+$' | awk '{printf "%.0f", $1/1048576}')
    [ "${u:-9999}" -lt 3500 ] && break
    sleep 5
  done
  setsid nohup stdbuf -oL -eL $B -m "$model" -ngl 99 -c 32768 -np 1 -fa on --kv-unified \
    -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto -n 4096 \
    --reasoning-effort medium --min-p 0 \
    --jinja --host 127.0.0.1 --port 8090 > $LOG 2>&1 < /dev/null &
  local i=0
  while [ $i -lt 300 ]; do
    [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:8090/health 2>/dev/null)" = "200" ] && break
    pgrep -x llama-server >/dev/null || { echo "ARM $tag: server died"; return 1; }
    i=$((i+1)); sleep 2
  done
  echo "ARM $tag ready after $((i*2))s"
  cd $BENCH
  .venv/bin/python -m hermesbench run --model "GSQ-RCO-$tag-VBR-noMTP" \
    --base-url http://127.0.0.1:8090/v1 --all --toolsets all \
    --timeout-overhead 900 --run-id bitdepth_${tag}_v5
  echo "ARM $tag DONE $(date -Iseconds)"
}
arm iq3xxs /mnt/TG_2TB/AI/Models/gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf
arm iq2xs  /mnt/TG_2TB/AI/Models/gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ2_XS-mtp.gguf
echo "BITDEPTH RUNS COMPLETE $(date -Iseconds)"
