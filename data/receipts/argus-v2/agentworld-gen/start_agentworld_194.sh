#!/usr/bin/env bash
# AgentWorld-35B-A3B on .194 GPUs {0,1} -- the socket-0 PHB pair.
#
# arch is `qwen35moe`, which is NOT on the -sm tensor deny list (that is
# qwen4exp/Flash-Next, upstream #27941), so tensor split is legal here.
set -euo pipefail

BIN=/home/mark/buun-llama-cpp/build_sm60_0920/bin/llama-server   # buun 08826ad6, the pinned fleet commit
MODEL=/home/mark/models/Qwen-AgentWorld-35B-A3B-UD-IQ4_XS.gguf
PIDF=/home/mark/agentworld.pid
LOG=/home/mark/agentworld.log

# NCCL aborts on this box; the var must be set even though sm_60 fails the cc>=700
# check and internal never actually engages. See [[allreduce-internal-inert-on-pascal]].
export GGML_CUDA_ALLREDUCE=internal
export CUDA_VISIBLE_DEVICES=0,1

# KV type is passed EXPLICITLY: buun defaults -ctk/-ctv to vbr, and an unstated
# default is how a config silently becomes a variable. See [[buun-default-kv-is-vbr]].
numactl --cpunodebind=0 --membind=0 "$BIN" \
    -m "$MODEL" \
    -c 16384 \
    -ngl 99 \
    -sm tensor \
    -fa on \
    -ctk f16 -ctv f16 \
    -np 1 \
    --host 0.0.0.0 --port 8082 \
    --jinja \
    --reasoning off \
    > "$LOG" 2>&1 &

echo $! > "$PIDF"     # record at launch; never search a process list for it later
echo "llama-server pid $(cat "$PIDF"), log $LOG"
