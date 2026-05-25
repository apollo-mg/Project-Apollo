#!/bin/bash
# Runner script for GigaChat 3.1 Lightning (10B-A1.8B) MoE
# Optimized for ultra-high-speed local "front desk" assistant workloads.

MODEL_PATH="/mnt/TG_2TB/Projects/Apollo/models/GigaChat3.1-10B-A1.8B-Q4_K_M.gguf"

# Point to the compiled llama-cli
LLAMA_CLI="/mnt/TG_2TB/Projects/Apollo/llama.cpp/build/bin/llama-cli"

echo "[*] Launching GigaChat 3.1 Lightning (10B-A1.8B MoE)..."
echo "[*] Mode: Fast Assistant (MLA & MTP Optimized)"

$LLAMA_CLI \
    -m "$MODEL_PATH" \
    -c 32768 \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    -fa on \
    --temp 0.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00 \
    -n -1 \
    -p "You are a highly responsive local AI assistant. Your primary goal is to be fast, accurate, and concise. Introduce yourself briefly."
