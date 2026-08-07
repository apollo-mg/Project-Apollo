#!/usr/bin/env bash
# Swap .73 from the pruned arm to the BASE arm, same flags, and gate on expert_gating_func.
set -u
BIN=/home/mark/tom_default/build/bin
M="/mnt/models/AI_Models/GLM/4.7 Flash/GLM-4.7-Flash-Q6_K.gguf"
pkill -x llama-server            # -x exact name; -f would match this script's own cmdline
for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || break; sleep 1; done
pgrep -x llama-server >/dev/null && { echo "FATAL: old server still alive"; exit 1; }
sleep 3
setsid "$BIN/llama-server" -m "$M" -c 4096 -ngl 99 -sm layer -np 1 --jinja -v \
  --host 127.0.0.1 --port 8092 > /tmp/glm_base_load.log 2>&1 < /dev/null &
for i in $(seq 1 600); do
  curl -s -m 5 http://127.0.0.1:8092/health 2>/dev/null | grep -q '"ok"' && { echo READY; break; }
  sleep 2
done
grep -m2 -E "model params|expert_gating_func" /tmp/glm_base_load.log
