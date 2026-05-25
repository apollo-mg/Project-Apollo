#!/bin/bash
# High-Performance Server script for Qwen 3.5 35B MoE
# Optimizations: Speculative Decoding (0.8B Draft) OR Multimodal Vision

LLAMA_SERVER="/mnt/TG_2TB/Projects/Apollo/llama.cpp/build/bin/llama-server"
MODEL_PATH="/mnt/TG_2TB/Projects/Apollo/models/Qwen3.5-35B-A3B-UD-IQ2_XXS.gguf"
MMPROJ_PATH="/mnt/TG_2TB/Projects/Apollo/models/mmproj-BF16.gguf"
DRAFT_MODEL="/run/media/mark/Games 2TB/APOLLO_COLD_STORAGE/GGUF/Qwen3.5-0.8B-Q4_K_M.gguf"

# =========================================================
# SELECT YOUR MODE: "VISION" or "SPEED"
# VISION = Enables image parsing (Disables Speculative Decoding)
# SPEED  = Enables Speculative Decoding (Disables Vision)
# =========================================================
MODE="VISION"

echo "[*] Launching High-Performance Apollo API Server..."
echo "[*] Main Model: 35B MoE (IQ2_XXS)"
echo "[*] Context: 32k | KV Cache: Q8_0"

if [ "$MODE" = "VISION" ]; then
    echo "[*] Mode: VISION (Multimodal Enabled, Speculative Decoding Disabled)"
    $LLAMA_SERVER \
        -m "$MODEL_PATH" \
        --mmproj "$MMPROJ_PATH" \
        -c 32768 \
        --cache-type-k q8_0 \
        --cache-type-v q8_0 \
        -np 1 \
        --host 127.0.0.1 \
        --port 8082

elif [ "$MODE" = "SPEED" ]; then
    echo "[*] Mode: SPEED (Speculative Decoding ACTIVE, Vision Disabled)"
    $LLAMA_SERVER \
        -m "$MODEL_PATH" \
        -md "$DRAFT_MODEL" \
        --draft 16 \
        -c 32768 \
        --host 127.0.0.1 \
        --port 8082

else
    echo "[-] ERROR: Invalid MODE selected. Please choose 'VISION' or 'SPEED'."
    exit 1
fi
