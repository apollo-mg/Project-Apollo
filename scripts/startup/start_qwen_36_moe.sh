#!/bin/bash
# Sovereign Coordinator - TheTom ROCm RotorQuant (TQ4_1S/TQ3_1S) Fork
MODEL="/mnt/TG_2TB/AI/Models/Gemma 4/12b/Unsloth-gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"
SERVER="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin/llama-server"
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



# --- Engine Tuning ---
export TURBO_AUTO_ASYMMETRIC=0

# --- Launch Server ---
# Utilizing the new RotorQuant Asymmetric KV Caching
# -ctk q8_0 (8-bit keys for quality)
# -ctv turbo4 (4-bit 1-Step sparse rotors for values - massive speedup)
# For vision, add:
# --mmproj "/mnt/TG_2TB/AI/Models/Qwen 3.5/27B/Huihui-Qwopus3.5-27B-v3-abliterated.mmproj-Q8_0.gguf" \
# below.
#For Qwen MTP add     --spec-type draft-mtp --spec-draft-n-max 3 \

$SERVER -m "$MODEL" \
    -c 75000 \
    -b 1024 \
    -ub 512 \
    -ctk q8_0 \
    -ctv turbo4 \
    --kv-unified \
    --cache-idle-slots \
    --cache-ram 2048 \
    -cb \
    -fa on \
    -fit off \
    -np 1 \
    -ngl 999 \
    --port 8082 \
    --host 0.0.0.0 \
    --chat-template-kwargs '{"enable_thinking": true}' \
    --model-draft "/mnt/TG_2TB/AI/Models/Gemma 4/12b/mtp-gemma-4-12B-it.gguf" \
    --spec-type draft-mtp --spec-draft-n-max 3
# For vision uncomment:
#    --mmproj "/mnt/TG_2TB/AI/Models/Qwen 3.5/27B/Huihui-Qwopus3.5-27B-v3-abliterated.mmproj-Q8_0.gguf" \

