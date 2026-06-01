---
name: fix-multimodal-llama-cpp-assertion
description: Fix the "non-causal attention requires n_ubatch >= n_tokens" assertion crash in llama.cpp during vision inference.
---

## When to Use
Use this skill when a multimodal (vision) model server (`llama-server`) crashes immediately after receiving an image inference request, specifically when the logs show a `GGML_ASSERT` failure related to `n_ubatch` and `n_tokens`.

## Procedure

### 1. Identify the Crash
Check the server logs (e.g., `rotorquant_vision_test.log`) for the following assertion:
```text
GGML_ASSERT((cparams.causal_attn || cparams.n_ubatch >= n_tokens_all) && "non-causal attention requires n_ubatch >= n_tokens") failed
```

### 2. Understand the Root Cause
- **Text Inference:** Causal (one token at a time). Works fine with small micro-batches (e.g., `-ub 64`).
- **Vision Inference:** Non-causal. The model must process all image patches (tokens) simultaneously.
- **The Crash:** If the micro-batch size (`-ub`) is smaller than the number of image tokens (typically 245-271 for models like Gemma 4 or LLaVA), the server crashes to prevent memory corruption.

### 3. Apply the Fix
Modify the `llama-server` launch script to increase the micro-batch size (`-ub`) to a value equal to or greater than the image token count.
- **Recommended Value:** `-ub 512` (This provides a safe buffer for most current vision encoders).
- **Example Change:**
  ```bash
  # Change this:
  -b 512 -ub 64
  # To this:
  -b 512 -ub 512
  ```

## Pitfalls and Fixes
- **Symptom:** Performance degradation or VRAM OOM during long prompts.
  - **Cause:** Increasing `-ub` increases the peak memory required for prompt processing (prefill).
  - **Fix:** If VRAM is tight, keep the batch size (`-b`) and micro-batch size (`-ub`) aligned at 512, but monitor VRAM closely. Avoid values like 1024+ unless the hardware has 24GB+ VRAM.

## Verification
1. Restart the server with the updated `-ub 512` flag.
2. Send a vision inference request with a local image (e.g., using a Python `urllib` script to `http://127.0.0.1:8082/v1/chat/completions`).
3. Confirm the server returns a valid response without crashing.
