---
name: patch-rocm-moe-kernel
description: Fix MUL_MAT_ID crash on AMD RDNA 4 (gfx1201) when running MoE models in llama.cpp.
---

## When to Use
Use this skill if you encounter `MUL_MAT_ID failed` or `ROCm error: unspecified launch failure` during prompt prefilling or background scans on an AMD RX 9000-series GPU using Mixture of Experts (MoE) models (e.g., Gemma 4, Qwen MoE). This is a known bug in the `MMQ` kernel path for RDNA 4.

## Procedure
1. Locate the `llama.cpp` source code directory (e.g., `/mnt/TG_2TB/Projects/Apollo/tmp/llama_cpp_gemma4/`).
2. Open `ggml/src/ggml-cuda/mmvq.cu`.
3. Locate the function `get_mmvq_mmid_max_batch_rdna4(ggml_type type)`.
4. Use the `replace` tool to modify the case for `GGML_TYPE_IQ2_XXS` (or the specific quantization you are using) to return `MMVQ_MAX_BATCH_SIZE`.

   ```cpp
   // Old code snippet
   case GGML_TYPE_IQ2_XXS: return 4;
   
   // New code snippet
   case GGML_TYPE_IQ2_XXS: return MMVQ_MAX_BATCH_SIZE; // FORCE MMVQ for RDNA 4 stability
   ```

5. Recompile `llama.cpp` using all available threads:
   ```bash
   cd build && cmake --build . -j$(nproc)
   ```
6. Restart the `llama-server` process.

## Pitfalls and Fixes
- **Symptom:** `MUL_MAT_ID` error persists for other quantizations.
  - **Cause:** The threshold is still too low for the active model type.
  - **Fix:** Update the `default` return or specific `GGML_TYPE_*` case in `get_mmvq_mmid_max_batch_rdna4` to return `MMVQ_MAX_BATCH_SIZE`.

## Verification
1. Run a large context injection test (7000+ tokens) to trigger multi-batch prefilling.
   ```python
   # Example verification script
   import requests
   prompt = "A" * 7168
   payload = {"messages": [{"role": "user", "content": prompt}], "max_tokens": 10}
   res = requests.post("http://127.0.0.1:8082/v1/chat/completions", json=payload)
   print(f"Status Code: {res.status_code}")
   ```
2. Monitor `llama-server.log` for errors.
