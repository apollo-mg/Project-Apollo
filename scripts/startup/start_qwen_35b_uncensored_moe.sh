#!/bin/bash
# Sovereign Architect Qwen 3.5 35B MoE - Uncensored Instruct - IQ2_M TurboQuant CONFIG
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/35B-A3B/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive-IQ2_M.gguf"
SERVER="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build_rocm/bin/llama-server"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):$LD_LIBRARY_PATH"

echo "[*] Launching Qwen 3.5 35B MoE Uncensored Architect (IQ2_M TurboQuant Mode)..."

# --- ROCm Performance & Stability Stack ---
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export HSA_ENABLE_SDMA=1 
export HSA_XNACK=0

# Qwen MoEs on ROCm 7.1.1 might suffer from MUL_MAT_ID kernel bugs if unstable.
export GGML_HIP_FORCE_MMQ=1

# --- Launch Server ---
# Note: Using TurboQuant (turbo3) for massive context window expansion on the RX 9070 XT.
$SERVER -m "$MODEL" \
    -c 65536 \
    -b 512 \
    -ub 512 \
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
