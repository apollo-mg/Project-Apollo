#!/bin/bash
# Sovereign Coordinator - TheTom ROCm RotorQuant (TQ4_1S/TQ3_1S) Fork
MODEL="/mnt/TG_2TB/AI/Models/Gemma 4/gemma-4-26B-A4B-it-UD-Q3_K_M.gguf"
SERVER="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build_rocm/bin/llama-server"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):$LD_LIBRARY_PATH"

echo "[*] Launching Coordinator (TheTom RotorQuant Mode)..."

# --- ROCm Stability Stack ---
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export HSA_ENABLE_SDMA=1
export AMDGPU_CWSR_ENABLE=1
export HSA_XNACK=0

# --- Launch Server ---
# Utilizing the new RotorQuant Asymmetric KV Caching
# -ctk q8_0 (8-bit keys for quality)
# -ctv turbo4 (4-bit 1-Step sparse rotors for values - massive speedup)
$SERVER -m "$MODEL" \
    --mmproj "/mnt/TG_2TB/AI/Models/Gemma 4/unsloth-gemma-4-26b-a4b-mmproj-BF16.gguf" \
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
    --chat-template-kwargs '{"enable_thinking":true}'
