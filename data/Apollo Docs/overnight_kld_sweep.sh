#!/bin/bash
set -e

BIN=/home/mark/llama-cpp-turboquant/build/bin
MODEL="/home/mark/AI/Models/Qwen 3.6/27B/Qwopus/Qwopus/Coder/Qwopus3.6-27B-Coder-heretic-Q6_K.gguf"
DATA=/home/mark/wikitext-2-raw/wiki.test.raw
BASE=/home/mark/turbo-logits-kld

echo "Generating 16k f16 base at 10 chunks (~41 GB)..."
"$BIN/llama-perplexity" -m "$MODEL" -f "$DATA" \
  -ctk f16 -ctv f16 -fa on -ngl 99 \
  -c 16384 --chunks 10 \
  --save-all-logits "$BASE/base_q6_f16kv_ctx16384_10ch.kld"

echo "Updating tier map in kv_common.sh..."
sed -i 's#16384:base_q6_f16kv_ctx16384_18ch.kld:18#16384:base_q6_f16kv_ctx16384_10ch.kld:10#' \
  /home/mark/kv-eval-pack-20260707/kld-panel/kv_common.sh

echo "Starting sweep..."
cd /home/mark/kv-eval-pack-20260707/kld-panel
TURBO_AUTO_ASYMMETRIC=0 \
BIN_DIR="$BIN" MODEL="$MODEL" DATASET="$DATA" BASE_DIR="$BASE" \
TYPES="turbo4 q8_0" \
./kv_kld_sweep.sh /home/mark/llama-cpp-turboquant/build/bin
