#!/usr/bin/env bash
# Serve one Qwen 3.8 27B quant on the RX 9070 XT, fully resident.
#
# Deliberately WITHOUT the tuned serving recipe (-ctk q8_0 -ctv turbo4 --kv-unified
# --cache-idle-slots, MTP draft). Those are the production defaults in
# scripts/startup/, but each is a variable that would confound a quant comparison.
# f16 KV, no speculative decoding, no repacking games. Quant is the only thing
# that changes between arms.
#
# usage: serve.sh <path-to-gguf>
set -u
M="${1:?usage: serve.sh <model.gguf>}"
SERVER="${SERVER:-/home/mark/moe-cache-test/src/build-hip/bin/llama-server}"
[ -x "$SERVER" ] || { echo "no server at $SERVER"; exit 1; }
export LD_LIBRARY_PATH="$(dirname "$SERVER"):${LD_LIBRARY_PATH:-}"

# RDNA4 stability stack, per scripts/startup/ — these are hardware requirements,
# not tuning knobs, so they stay on.
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export HSA_ENABLE_SDMA=1
export AMDGPU_CWSR_ENABLE=0

echo "### $(basename "$M")"
rocm-smi --showclocks --showpower 2>/dev/null | grep -iE "sclk|power" | head -4

exec "$SERVER" -m "$M" \
  -c 8192 \
  -ngl 999 \
  -fa on \
  -np 1 \
  --port 8082 --host 127.0.0.1
