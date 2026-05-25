#!/bin/bash
# Sovereign Coordinator - Gemopus APEX I-Mini
# Model: gemopus-4-26B-A4B-APEX-I-Mini (MoE Gradient Quantization w/ Imatrix)
MODEL="/mnt/TG_2TB/AI/Models/Gemma 4/26B-A4B/gemopus-4-26B-A4B-APEX-I-Mini.gguf"
SERVER="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build_rocm/bin/llama-server"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):$LD_LIBRARY_PATH"

echo "[*] Launching Coordinator (Gemopus APEX I-Mini)..."

# --- ROCm Stability Stack ---
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export HSA_ENABLE_SDMA=1
export AMDGPU_CWSR_ENABLE=1
export HSA_XNACK=0

# --- Launch Server ---
# Note on KV Cache: Since the APEX I-Mini model is only ~13GB, it leaves more VRAM 
# headroom than standard 8-bit quants. 
# Keeping RotorQuant (-ctk q8_0, -ctv turbo4) for 64k context, but you can likely 
# afford to bump -ctv to q8_0 if you want maximum reasoning precision.

# For vision add     --mmproj "/mnt/TG_2TB/AI/Models/Gemma 4/unsloth-gemma-4-26b-a4b-mmproj-BF16.gguf" \
# below.

$SERVER -m "$MODEL" \
    -c 65536 \
    -b 512 \
    -ub 512 \
    -ctk q8_0 \
    -ctv turbo4 \
    -cb \
    -fa on \
    -np 1 \
    -ngl 99 \
    --cache-ram 2048 \
    --port 8082 \
    --host 0.0.0.0 \
    --jinja \
    --mlock \
    --no-kv-offload \
    --chat-template-kwargs '{"enable_thinking":false}'
