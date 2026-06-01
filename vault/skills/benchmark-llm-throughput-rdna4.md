---
name: benchmark-llm-throughput-rdna4
description: Benchmarking procedure for LLM throughput (tokens/sec) and VRAM stability on AMD RDNA 4 (RX 9070 XT) using llama.cpp and RotorQuant. Use when optimizing local inference settings, testing speculative decoding, or diagnosing memory bandwidth bottlenecks.
---

# Benchmarking LLM Throughput and VRAM Stability on RDNA 4

This skill provides a procedure for empirical benchmarking of local LLMs on the AMD RX 9070 XT (gfx1201) to identify hardware bottlenecks and validate optimization patches (like TurboQuant or Speculative Decoding).

## Triggers
- You are asked to optimize `tokens/second` (t/s) for local models.
- You are testing new `llama.cpp` flags (e.g., `--spec-type ngram-mod`, `-ctv turbo4`).
- The model is suspected of being "Memory Bandwidth Bound" vs "Compute Bound."
- You need to validate that a VRAM leak or fragmentation issue is resolved.

## Procedure

### 1. Establish a VRAM Baseline
Before testing, record the static VRAM usage of the model when idle but loaded.
- Run `rocm-smi` or use the `system_metrics` tool.
- **Goal:** For a 27B model at `IQ3_M` quantization with 64k context, target ~15,200 MB usage on a 16GB card.

### 2. Implement the Repetitive Benchmark Script
Speculative decoding and throughput optimizations often shine on repetitive boilerplate (JSON/Code). Use a script to force high-hit-rate predictive generation.

Create `benchmark_sd.py`:
```python
import time
import requests
import json

url = "http://localhost:8082/v1/chat/completions"
headers = {"Content-Type": "application/json"}
payload = {
    "model": "Qwopus-27B",
    "messages": [{"role": "user", "content": "Generate a massive JSON array of 50 fake users with 'id', 'name', and 'email' fields."}],
    "temperature": 0.0,
    "max_tokens": 4000
}

print("Starting benchmark...")
start = time.time()
response = requests.post(url, headers=headers, data=json.dumps(payload))
end = time.time()

if response.status_code == 200:
    data = response.json()
    tokens = data['usage']['completion_tokens']
    duration = end - start
    print(f"\n--- Results ---")
    print(f"Total Time: {duration:.2f} seconds")
    print(f"Tokens Generated: {tokens}")
    print(f"Speed: {tokens/duration:.2f} tokens/second")
else:
    print(f"Error: {response.status_code}")
```

### 3. Test Optimization Flags
Modify your `llama-server` startup script (`start_qwen_36_moe.sh` or similar) and run the benchmark for each:

- **Speculative Decoding (N-Gram):**
  ```bash
  --spec-type ngram-mod --draft 16
  ```
- **TurboQuant Asymmetric KV:**
  ```bash
  -ctk q8_0 -ctv turbo4
  ```

### 4. Diagnose Bottlenecks
Compare results across runs:
- **Baseline Doubled?** If removing `--no-kv-offload` doubles speed (e.g., 13 t/s -> 26 t/s), the initial bottleneck was **PCIe Bandwidth**.
- **No Speedup with Flags?** If `--spec-type ngram-mod` results in 0.0 change (e.g., 26.16 t/s vs 26.17 t/s), the GPU is **Memory Bandwidth Bound**.
- **Hardware Wall:** For the RX 9070 XT (256-bit bus, ~576 GB/s), a 27B model (12-13GB weights) has a theoretical max of ~48 t/s. In practice, 25-27 t/s is optimized.

## Verification Checklist
- [ ] VRAM usage remained static during prefill (no `ggml_cuda_pool_leg` creep).
- [ ] `llama-bench` confirmed that `q8_0/turbo4` allocated 65k context successfully while `f16` OOMed.
- [ ] Benchmark hit at least 25 t/s for 27B class models.

## Landmines and Pitfalls
- **The "2-Bit Drunk" Loop:** Aggressive quantization (`IQ3_XXS`) on MoE models can cause "sticky" attention, repeating sentences endlessly. If this happens, drop temperature or increase bit-depth.
- **Gemma 4 Exception:** Gemma 4 uses `head_dim=512`. Workarounds for `head_dim <= 256` will NOT fix VRAM creep for Gemma 4's full attention layers.
