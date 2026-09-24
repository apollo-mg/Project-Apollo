#!/bin/bash
# PREREG_SPLIT_PREFILL_73.md. Runs on the desktop; drives .73 over ssh. ./run_legs.sh [LEG...]  (default: T L L4)
# The wake proxy must be stopped first (it would relaunch the daily server or suspend .73 mid-leg).
set -u
D=$(cd "$(dirname "$0")" && pwd); mkdir -p "$D/raw"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
BIN='~/buun-llama-cpp/build_sm60_0920/bin/llama-server'   # buun 08826ad6e
COMMON="-m '/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf' --mmproj '/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf' -ngl 99 -c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -fit off -fa on --spec-type draft-mtp --draft-max 3 --jinja --kv-unified --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 0.0 --host 0.0.0.0 --port 8080"
systemctl --user is-active -q apollo-wake-proxy && { echo "ABORT: wake proxy is running"; exit 2; }
for LEG in "${@:-T L L4}"; do for LEG in $LEG; do
  case $LEG in T) SM=tensor NP=1 MODE=depth;; L) SM=layer NP=1 MODE=depth;; L4) SM=layer NP=4 MODE=reuse;;
    *) echo "unknown leg $LEG"; continue;; esac
  echo "######## $LEG sm=$SM np=$NP $(date -Is)"
  ssh 10.0.0.73 "pgrep -x llama-server" && { echo "ABORT: a llama-server is already running on .73"; exit 2; }
  ssh 10.0.0.73 "mkdir -p ~/split73; nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader > ~/split73/$LEG.clocks; setsid nohup $BIN $COMMON -sm $SM -np $NP > ~/split73/$LEG.log 2>&1 < /dev/null & echo \$! > ~/split73/$LEG.pid"
  timeout 7200 $PY "$D/bench73.py" $MODE $LEG "$D/raw/$LEG.jsonl"; rc=$?
  echo "   bench rc=$rc"
  ssh 10.0.0.73 "P=\$(cat ~/split73/$LEG.pid); if kill -0 \$P 2>/dev/null; then echo ALIVE_AT_END; kill \$P; else echo DEAD_AT_END; fi; for i in \$(seq 30); do kill -0 \$P 2>/dev/null || break; sleep 1; done; pgrep -x llama-server && echo STILL_RUNNING || echo stopped; grep -c -E 'ggml_abort|GGML_ASSERT|SIGABRT|Aborted' ~/split73/$LEG.log"
done; done
echo "######## LEGS DONE $(date -Is)"
