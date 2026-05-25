#!/bin/bash
# Sovereign Architect Gemma 4 26B MoE - RDNA 4 HARD-STABILITY CONFIG
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/27B/Qwopus3.5-27B-v3-Q2_K.gguf"
SERVER="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_gemma4/build/bin/llama-server"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):$LD_LIBRARY_PATH"

echo "[*] Launching Gemma 4 26B MoE Architect (RDNA 4 Stability Mode)..."

# --- ROCm Stability Stack ---
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export GGML_HIP_FORCE_MMQ=1
export HSA_ENABLE_SDMA=0
export AMDGPU_CWSR_ENABLE=0
export HSA_XNACK=0

# --- Launch Server ---
# We have bypassed the MUL_MAT_ID MoE kernel bug via a source code patch (forcing MMVQ).
# Reverting to the proven MoE Micro-Batching (-ub 64) and TurboQuant Asymmetric KV Caching (-ctk q8_0 -ctv turbo3) to prevent overnight crashes.
$SERVER -m "$MODEL" \
    -c 65536 \
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
