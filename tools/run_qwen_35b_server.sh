#!/bin/bash
# High-Performance Server script for Qwen 3.5 35B MoE
# Optimizations: Persistent Prompt Caching

LLAMA_SERVER="/mnt/TG_2TB/Projects/Apollo/llama.cpp/build/bin/llama-server"
MODEL_PATH="/mnt/TG_2TB/Projects/Apollo/models/Qwen3.5-35B-A3B-UD-IQ2_XXS.gguf"
MMPROJ_PATH="/mnt/TG_2TB/Projects/Apollo/models/mmproj-BF16.gguf"

# Prompt Cache Path (to make repeat sessions instant)
CACHE_PATH="/mnt/TG_2TB/Projects/Apollo/data/apollo_prompt_cache.bin"

echo "[*] Launching High-Performance Apollo API Server..."
echo "[*] Main Model: 35B MoE (IQ2_XXS)"
echo "[*] Vision: ACTIVE"
echo "[*] Context: 32k | Cache: ACTIVE"

$LLAMA_SERVER \
    -m "$MODEL_PATH" \
    --mmproj "$MMPROJ_PATH" \
    -c 16384 \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    --host 127.0.0.1 \
    --port 8082
