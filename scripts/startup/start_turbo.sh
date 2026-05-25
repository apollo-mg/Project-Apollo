#!/bin/bash
# Sovereign Architect Gemma 4 26B MoE - TurboQuant Extended Context
MODEL="/mnt/TG_2TB/AI/Models/Gemma 4/gemma-4-26B-A4B-it-UD-IQ2_XXS.gguf"
SERVER="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build_rocm/bin/llama-server"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):$LD_LIBRARY_PATH"

echo "[*] Launching Gemma 4 26B MoE Architect (TurboQuant Asymmetric Cache Mode)..."
echo "[*] Context expanded to 65,536 tokens!"

# --- ROCm Stability Stack ---
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export GGML_HIP_FORCE_MMQ=1
export HSA_ENABLE_SDMA=0
export AMDGPU_CWSR_ENABLE=0
export HSA_XNACK=0

# --- Launch Server ---
# MUL_MAT_ID RDNA 4 bug patched in source.
# Using Q8_0 for Keys (high accuracy) and TQ3_0 for Values (extreme compression)
$SERVER -m "$MODEL" \
    -c 65536 \
    -b 512 \
    -ub 128 \
    -ctk q8_0 \
    -ctv turbo3 \
    -cb \
    -fa on \
    -np 1 \
    -ngl 99 \
    --cache-ram 0 \
    --no-cache-prompt \
    --port 8082 \
    --host 0.0.0.0
