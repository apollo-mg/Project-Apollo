#!/bin/bash
# Sovereign Architect Gemma 4 26B MoE - Q3_K_M EXPERIMENTAL CONFIG
MODEL="/mnt/TG_2TB/AI/Models/Gemma 4/unsloth-gemma-4-26B-A4B-it-UD-IQ2_M_(fixed).gguf"
SERVER="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_gemma4/build/bin/llama-server"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):$LD_LIBRARY_PATH"

echo "[*] Launching Gemma 4 26B MoE Architect (Q3_K_M Tank Mode)..."

# --- ROCm Performance & Stability Stack ---
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export HSA_ENABLE_SDMA=1 
export HSA_XNACK=0

# MoE models on ROCm 7.1.1 can still suffer from MUL_MAT_ID kernel bugs. 
# Re-enabling MMQ force to prevent instant segfaults during matrix multiplication.
#export GGML_HIP_FORCE_MMQ=1






# --- Launch Server ---
# Note: Gemma 4 build does not support TurboQuant yet, falling back to standard q8_0 / q8_0 KV caching.
# Q3_K_M is smaller, so we can try a slightly larger context window if desired, but keeping at 32768 for safety.
$SERVER -m "$MODEL" \
    -c 32768 \
    -b 512 \
    -ub 512 \
    -ctk q8_0 \
    -ctv q4_0 \
    -cb \
    -fa on \
    -np 1 \
    -ngl 99 \
    --cache-ram 0 \
    --port 8082 \
    --host 0.0.0.0 \
    --jinja \
    --chat-template-kwargs '{"enable_thinking":false}'
