#!/bin/bash
# Runner script for Crow-9B-HERETIC-4.6 (9B Dense)
# Optimized using a hybrid of Unsloth's Qwen 3.5 9B Thinking settings 
# and the model creator's (Crownelius) precision recommendations.

MODEL_PATH="/mnt/TG_2TB/Projects/Apollo/models/Crow-9B-HERETIC-4.6.i1-Q6_K.gguf"
MMPROJ_PATH="/mnt/TG_2TB/Projects/Apollo/models/Crow-9B-Opus-4.6-Distill-Heretic_Qwen3.5.mmproj-f16.gguf"

# Point to the compiled llama-cli
LLAMA_CLI="/mnt/TG_2TB/Projects/Apollo/llama.cpp/build/bin/llama-cli"

# System Prompt from model creator
SYSTEM_PROMPT="You are Crow, a precise and capable assistant for reasoning, writing, coding, and long-form dialogue. Behavior rules:
- Answer the user's actual request directly.
- Be accurate, complete, and structured.
- Think before answering, but do not get stuck in repetitive loops or meta-commentary.
- If the request is ambiguous or incomplete, state what is missing and make the smallest reasonable assumption needed to continue.
- If the user wants analysis or technical help, prefer concrete steps, examples, and decisions over fluff.
- Finish with a usable answer, not just planning."

echo "[*] Launching Crow 9B HERETIC (9B Dense)..."
echo "[*] Mode: Hybrid Thinking (Unsloth + Crow Parameters)"

$LLAMA_CLI \
    -m "$MODEL_PATH" \
    --mmproj "$MMPROJ_PATH" \
    -c 32768 \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    --temp 1.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00 \
    --repeat-penalty 1.05 \
    --presence-penalty 1.5 \
    -n -1 \
    -p "<|im_start|>system
$SYSTEM_PROMPT<|im_end|>
<|im_start|>user
Introduce yourself and explain your architectural strengths.<|im_end|>
<|im_start|>assistant
"
