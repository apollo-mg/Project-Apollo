---
name: benchmark-vision-stability-rdna4
description: Benchmarking procedure for multimodal (vision) LLMs on AMD RDNA 4 (RX 9070 XT) to ensure ROCm stability.
---

## When to Use
Use this skill when integrating vision capabilities (e.g., Gemma 4 + `mmproj`) on AMD RDNA 4 hardware or when experiencing `Illegal Memory Access` crashes during image inference.

## Procedure

### 1. Identify Vision Assets
Locate the base LLM GGUF and its corresponding multimodal projection module (`mmproj`).
- Example: `unsloth-gemma-4-26b-a4b-mmproj-BF16.gguf`

### 2. Set ROCm Environment Variables
Set these critical flags to stabilize RDNA 4 (gfx1201) during vision operations:
```bash
export HSA_OVERRIDE_GFX_VERSION=12.0.1
export HSA_ENABLE_SDMA=1
export HSA_XNACK=0
```

### 3. Optimize Launch Arguments
Tune the `llama-server` (or `llama-cli`) to handle non-causal attention and image tokenization without crashing.
- `-ub 512`: **Critical.** Increasing the micro-batch size from 64 to 512 resolves non-causal attention crashes on RDNA 4.
- `--mmproj <path>`: Link the vision module.
- `-ctk q8_0 -ctv q4_0`: Use asymmetric KV caching to manage VRAM pressure.

**Benchmark Launch Example:**
```bash
./llama-server -m models/gemma-4-26B.gguf \
    --mmproj models/vision-module.gguf \
    -c 16384 -ub 512 -ctk q8_0 -ctv q4_0 -fa on -ngl 99
```

### 4. Verification Test
Send a request with an image path to verify the "Vision Encoding" and "Reasoning" speeds.
```bash
# Example using an image in the project root
curl -X POST http://localhost:8082/completion -d '{ 
  "prompt": "Describe this image in one sentence.",
  "image_data": [{"data": "..."}]
}'
```

## Pitfalls and Fixes
- **Symptom:** `HIP error: an illegal memory access` or `MUL_MAT_ID` crash during the "Vision Encoding" phase.
  - **Cause:** Micro-batch size (`-ub`) is too small for non-causal attention on RDNA 4.
  - **Fix:** Increase `-ub` to 512 or higher.
- **Symptom:** Vision test succeeds in a sandbox but fails on the host (or vice versa).
  - **Cause:** Tool sandboxing (e.g., `bwrap`) may be masking GPU device nodes (`/dev/kfd`), causing a silent fallback to CPU (AVX2).
  - **Fix:** Check `llama.cpp` logs for `failed to initialize ROCm: no ROCm-capable device is detected`. Ensure the sandbox allows access to `/dev/dri` and `/dev/kfd`.

## Verification
- Confirm blisstering prompt processing speeds (e.g., > 200 t/s for Vision Encoding).
- Verify the model correctly describes the contents of `test_known.jpg`.
