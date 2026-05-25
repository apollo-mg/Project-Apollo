#!/bin/bash
# Server script for Unsloth's Qwen3.5-35B-A3B MoE (UD-IQ2_XXS)
# Optimized for 16GB VRAM environments using Unsloth's recommended settings.

MODEL_PATH="/mnt/TG_2TB/Projects/Apollo/models/Crow-9B-HERETIC-4.6.i1-Q6_K.gguf"
MMPROJ_PATH="/mnt/TG_2TB/Projects/Apollo/models/Crow-9B-Opus-4.6-Distill-Heretic_Qwen3.5.mmproj-f16.gguf"

# Point to the compiled llama-server
LLAMA_SERVER="/mnt/TG_2TB/Projects/Apollo/llama.cpp/build/bin/llama-server"

echo "[*] Launching Crow9B API Server..."
echo "[*] Port: 8082 (Targeted by buddy_agent.py)"

$LLAMA_SERVER \
    -m "$MODEL_PATH" \
    --mmproj "$MMPROJ_PATH" \
    -c 131072 \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    --host 127.0.0.1 \
    --port 8082
