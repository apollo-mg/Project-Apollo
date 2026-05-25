#!/bin/bash
# Sovereign Architect Gemma 4 31B Dense - EXPERIMENTAL PERFORMANCE CONFIG
MODEL="/mnt/TG_2TB/AI/Models/Gemma 4/gemma-4-31B-it-UD-IQ2_M.gguf"
SERVER="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_gemma4/build/bin/llama-server"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):$LD_LIBRARY_PATH"

echo "[*] Launching Gemma 4 31B Architect (Performance Mode)..."

# --- ROCm Performance Stack ---
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export HSA_ENABLE_SDMA=1 
export HSA_XNACK=0
# Removed AMDGPU_CWSR_ENABLE=0 to unchain hardware scheduler
# Removed GGML_HIP_FORCE_MMQ=1 as this is a dense model and ROCm 7.1.1 math is stable

# --- Launch Server ---
# Note: Gemma 4 build does not support TurboQuant yet, falling back to standard q8_0 / q4_0 KV caching.
# Context size set to 16384 to ensure the 31B dense model fits in 16GB VRAM along with the KV cache.
$SERVER -m "$MODEL" \
    -c 16384 \
    -b 512 \
    -ub 512 \
    -ctk q8_0 \
    -ctv q8_0 \
    -cb \
    -fa on \
    -np 1 \
    -ngl 99 \
    --cache-ram 0 \
    --port 8082 \
    --host 0.0.0.0 \
    --jinja \
    --chat-template-kwargs '{"enable_thinking":false}'
