---
name: benchmark-edge-llm-performance
description: Benchmarking procedure for edge LLMs (Pi 5, mobile) comparing speed, behavior, and resource efficiency.
---

## When to Use
Use this skill when evaluating new models for edge deployment (e.g., Pi 5, Snapdragon/Exynos mobile) or when optimizing background service configurations. Use this to conduct an "Edge Shootout" between competing quantizations or architectures.

## Procedure

### 1. Quiesce Services
Stop background servers to ensure the CPU/RAM is dedicated to the benchmark.
```bash
sudo systemctl stop bonpi.service  # Or equivalent
```

### 2. Standardize Hardware Baseline
Verify no other heavy processes are running.
```bash
top -n 1 -b | head -n 20
```

### 3. Conduct the "Edge Shootout"
Run identical test prompts across different models using `llama-cli`.
- **Parameter Check:** Compare 2B models (faster logic) vs 8B models (broader knowledge).
- **Quantization Check:** Compare 1-bit (fast, low knowledge density) vs 3-bit/4-bit (slower, smarter).

**Benchmark Command Example:**
```bash
./llama-cli -m models/model.gguf -p "Explain quantum computing in one simple sentence." -n 128 -c 512
```

### 4. Metrics Collection
Capture and compare:
- **Prompt Processing Speed:** Measured in tokens per second (t/s).
- **Generation Speed:** Measured in t/s.
- **Behavioral Profile:** Identify if the model uses Chain-of-Thought (CoT) by checking for `<think>` blocks or explicit reasoning steps.

## Pitfalls and Fixes
- **Symptom:** Small model (2B) is slower than a large model (8B).
  - **Cause:** CPU bottleneck or lack of SIMD (NEON/AVX) optimizations for a specific quantization type (e.g., TurboQuant fallback to Scalar C).
  - **Fix:** Check source code for `__ARM_NEON` support for the specific quantization type.
- **Symptom:** Model burns through context window too fast.
  - **Cause:** Chain-of-Thought (CoT) fine-tuning forces the model to reason explicitly, consuming tokens for logic before the final answer.
  - **Fix:** Use CoT models for complex logic tasks only; use direct-answer models for simple retrieval.

## Verification
- Confirm that t/s values are reported in the CLI output.
- Verify that the model's behavioral profile (CoT vs Direct) is logged for architectural decision-making.
