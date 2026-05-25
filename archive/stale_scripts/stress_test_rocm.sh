#!/bin/bash
# AI Compute Stress Test for RX 9070 XT Undervolt
# This script repeatedly runs a massive context prompt through the Gemma 4 MoE model.
# It is designed to cause the exact transient power spikes that crash unstable undervolts.

MODEL="/mnt/TG_2TB/AI/Models/Gemma 4/gemma-4-26B-A4B-it-UD-Q3_K_M.gguf"
CLI="/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build_rocm/bin/llama-cli"

if [ ! -f "$CLI" ]; then
    echo "Error: llama-cli not found at $CLI"
    exit 1
fi

echo "====================================================="
echo "  RX 9070 XT AI Compute Stress Test (Undervolt)      "
echo "====================================================="
echo "This test will hit your matrix math cores with massive"
echo "transient loads. Monitor your voltage in LACT."
echo "Press Ctrl+C to stop the test."
echo ""

# ROCm Stability Stack
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export HSA_ENABLE_SDMA=1

LOOP_COUNT=1

while true; do
    echo "[Loop $LOOP_COUNT] Pounding matrix math cores and VRAM..."
    
    # We use a 32k context and a complex generation task to pin the compute units at 100%
    # The output is sent to /dev/null so you can focus on monitoring LACT
    $CLI -m "$MODEL" \
        -c 32768 \
        -b 512 \
        -ub 64 \
        -ctk q8_0 \
        -ctv turbo4 \
        -n 1024 \
        -ngl 99 \
        -p "Write a highly detailed, 10000-word comprehensive architectural analysis of Grouped Query Attention in modern LLMs, including its mathematical formulas, VRAM implications, and how it interacts with asymmetric KV caching (q8_0 keys and 4-bit values). Ensure the response is highly technical and exhaustive." < /dev/null > /dev/null 2>&1
        
    echo "[Loop $LOOP_COUNT] Evaluation finished. Transient power drop (GPU breathing)..."
    sleep 3
    ((LOOP_COUNT++))
done
