#!/bin/bash
# Sovereign Coordinator - TheTom ROCm RotorQuant (TQ4_1S/TQ3_1S) Fork
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/27B/Qwopus3.5-27B-v3.5-Q3_K_M.gguf"
SERVER="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build_rocm/bin/llama-server"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):$LD_LIBRARY_PATH"

echo "[*] Launching Coordinator (TheTom RotorQuant Mode)..."

# --- ROCm Stability Stack ---
export HSA_OVERRIDE_GFX_VERSION=12.0.1

# --- Memory Stability Tweaks
export HSA_ENABLE_SDMA=1
export AMDGPU_CWSR_ENABLE=0
#export HSA_XNACK=0
#export HIP_FORCE_DEV_KERNARG=1
# Test and try
export GGML_HIP_FORCE_MMQ=1



# --- Launch Server ---
# Utilizing the new RotorQuant Asymmetric KV Caching
# -ctk q8_0 (8-bit keys for quality)
# -ctv turbo4 (4-bit 1-Step sparse rotors for values - massive speedup)
# For vision, add:
# --mmproj "/mnt/TG_2TB/AI/Models/Qwen 3.5/27B/Huihui-Qwopus3.5-27B-v3-abliterated.mmproj-Q8_0.gguf" \
# below.

$SERVER -m "$MODEL" \
    -c 65536 \
    -b 8192 \
    -ub 1024 \
    -ctk q8_0 \
    -ctv turbo4 \
    -cb \
    -fa on \
    -np 2 \
    -ngl 99 \
    --port 8082 \
    --host 0.0.0.0 \
    --jinja \
    --chat-template-kwargs '{"enable_thinking":true}' \
    --cache-ram 8192 \
    --no-kv-offload
