---
name: optimize-multi-gpu-inference-without-nvlink
description: Optimize llama.cpp (llama-server) performance for multi-GPU setups (e.g., Tesla P100, P40) that lack NVLink or high-speed inter-GPU interconnects. Use when encountering low token-per-second (t/s) rates on multi-GPU nodes due to PCIe bandwidth bottlenecks.
---

# Optimize Multi-GPU Inference Without NVLink

Multi-GPU setups on older server hardware (e.g., Pascal Tesla P100/P40) or standard consumer motherboards often lack NVLink. By default, `llama.cpp` uses **Layer Splitting** (`-sm layer`), which transfers massive activation blocks across the PCIe bus, causing severe performance degradation.

## Procedure

### 1. Identify the Bottleneck
If your prompt evaluation or decoding speed is significantly lower than expected (e.g., < 10 t/s on high-end older GPUs), the PCIe bus is likely saturated by inter-GPU communication.

### 2. Switch to Row Splitting
Row splitting slices individual matrices across both GPUs. This allows GPUs to calculate math simultaneously and only exchange tiny result vectors over PCIe, drastically reducing bandwidth requirements.

- Append `-sm row` to your `llama-server` or `llama-cli` command.

### 3. Force Balanced Memory Allocation
Ensure the model is split evenly (or according to VRAM capacity) to prevent one GPU from idling.

- Use `-ts 1,1` for a 50/50 split on two identical GPUs.
- Adjust values (e.g., `-ts 1,2`) for disparate VRAM capacities.

### 4. Optimize Batching for Older Architectures
Pascal-era GPUs (P100, P40) benefit from smaller batch sizes to maintain steady pipelines.

- Use `-b 512 -ub 512` (physical and logical batch size) to stabilize the throughput.

## Example Launch Command

```bash
./llama-server \
  -m your_model_q4_k_m.gguf \
  -c 65536 \
  --host 0.0.0.0 \
  --port 8082 \
  -sm row \
  -ts 1,1 \
  -b 512 -ub 512
```

## Verification
- Monitor `nvidia-smi` or `rocm-smi` during generation.
- Both GPUs should show synchronized, high utilization (> 80%) during the decode phase.
- Token-per-second (t/s) should increase significantly (often 2x-3x over layer splitting).

## Pitfalls
- **Row Splitting and Flash Attention**: Ensure your `llama.cpp` build supports Flash Attention with row splitting; if it crashes, you may need to fallback to `-sm layer` but with `-ub` optimizations.
- **Heterogeneous GPUs**: Row splitting works best on identical GPUs. Mixing different generations (e.g., P100 and 3090) may lead to the slower GPU bottlenecking the faster one more severely than layer splitting would.
