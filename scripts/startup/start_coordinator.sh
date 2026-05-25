#!/bin/bash
# Sovereign Coordinator Qwopus 3.5 27B - TheTom ROCm TurboQuant Fork
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/27B/Qwopus3.5-27B-v3-Q2_K.gguf"
SERVER="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build_rocm/bin/llama-server"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):$LD_LIBRARY_PATH"

echo "[*] Launching Qwopus Coordinator (TheTom TurboQuant Mode)..."

# --- ROCm Stability Stack ---
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export HSA_ENABLE_SDMA=0
export AMDGPU_CWSR_ENABLE=0
export HSA_XNACK=0

# --- Launch Server ---
# Utilizing the TurboQuant Asymmetric KV Caching (-ctk q8_0 -ctv turbo3)
$SERVER -m "$MODEL" \
    -c 65536 \
    -b 512 \
    -ctk q8_0 \
    -ctv turbo3 \
    -cb \
    -fa on \
    -np 1 \
    -ngl 99 \
    --cache-ram 0 \
    --port 8082 \
    --host 0.0.0.0 \
    --jinja \
    --chat-template-kwargs '{"enable_thinking":false}'
