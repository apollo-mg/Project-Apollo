# TECHNICAL REFERENCE: RDNA 4 (GFX1201) ROCm 7.1.1 Stability
**Hardware:** AMD Radeon RX 9070 XT (16GB)
**Environment:** Ubuntu 22.04, PyTorch 2.9.1+rocm7.1.1

## 1. Known Kernel Quirks
*   **Linear Layer Crash:** Mixed precision (FP32 input * FP16 weights) can trigger HIP Illegal Memory Access on certain kernels.
*   **Solution:** Force cast all inputs to match weight dtypes before the operation.

## 2. Memory Management
*   **SDMA:** Generally stable on 7.1.1, but disable (`HSA_ENABLE_SDMA=0`) if Host-to-Device transfers show corruption.
*   **Contiguity:** ALWAYS enforce `.contiguous()` on tensors before moving them to the device to bypass DMA alignment bugs.

## 3. Power Monitoring
*   **Key:** ROCm reports power under `Average Graphics Package Power (W)` or `average_socket_power (W)`. 
*   **Note:** Some tools (like old rocm-smi) might show N/A; parse the raw JSON for the average socket keys instead.
