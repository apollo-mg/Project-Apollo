#!/bin/bash
# PREREG_SAGE.md server on .194: serve_sage.sh MODEL [TEMPLATE_FILE]. Upstream llama.cpp c7fc509 build_sm60 (as Ornith,
# Flint), 4x P100 layer split, F16 KV, one slot. GGML_CUDA_ALLREDUCE set because unset means NCCL, which aborts on .194.
BIN=$HOME/llama.cpp-flint/build_sm60/bin/llama-server
CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal exec "$BIN" -m "$1" -ngl 99 -sm layer -c 16384 -ctk f16 -ctv f16 \
  -np 1 -fit off --host 0.0.0.0 --port 8190 ${2:+--chat-template-file "$2"}
