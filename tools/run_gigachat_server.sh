#!/bin/bash
# Server script for GigaChat 3.1 Lightning (10B-A1.8B) MoE
# Optimized for ultra-high-speed local "front desk" assistant workloads.

MODEL_PATH="/mnt/TG_2TB/Projects/Apollo/models/GigaChat3.1-10B-A1.8B-Q4_K_M.gguf"

# Point to the compiled llama-server
LLAMA_SERVER="/mnt/TG_2TB/Projects/Apollo/llama.cpp/build/bin/llama-server"

echo "[*] Launching GigaChat 3.1 Lightning (10B-A1.8B MoE) API Server..."
echo "[*] Port: 8082 (Targeted by buddy_agent.py)"

$LLAMA_SERVER \
    -m "$MODEL_PATH" \
    -c 32768 \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    -fa on \
    --host 127.0.0.1 \
    --port 8082
