# 🛸 RDNA 4 (GFX1201) AI MASTER LIST
**Last Updated:** March 9, 2026 | **Environment:** ROCm 7.2 / Poachers Special Ed (PyTorch 2.9.1 / Triton 3.5.1)

## 🟢 1. THE "GREEN ZONE" (Verified Working Bare-Metal)
*   **CDNA 4 Intrinsics on RDNA 4**: **EASTER EGG UNLOCKED.** GFX1201 silently accepts data-center compiler intrinsics (`__builtin_amdgcn_s_barrier`, `__builtin_amdgcn_s_setprio`).
*   **8-Wave Ping-Pong Scheduling**: **VIABLE.** Hardware supports manual wave stalling and SIMD priority elevation, allowing simultaneous memory/compute overlapping to bypass driver bottlenecks.
*   **LDS Memory Swizzling**: **APPLICABLE.** XOR-based bank conflict resolution is viable for custom GEMM kernels.
*   **ComfyUI RX 9000 Optimizations**: Use `export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True` and `export HSA_ENABLE_SDMA=0` for maximum stability. Add `--reserve-vram 3` and disable cuDNN (`torch.backends.cudnn.enabled = False`) to prevent illegal memory access errors.
*   **ROCm 7.2 ThinLTO Support**: **CONFIRMED.** ROCm 7.2 compiler enables ThinLTO, allowing global optimization with near-local build speeds for PyTorch/Triton/XLA.
*   **JAX-AITER Integration**: **VIABLE.** AMD's AITER-optimized AI kernels (MHA/FMHA/GEMM) can be pulled into JAX workflows on ROCm via the `jax-aiter` bridge, achieving up to 4x-9x speedups in attention.
*   **Flash Linear Attention (FLA)**: **ASCENDED.** Liberated from Docker; running bare-metal via Triton kernels.
*   **4-bit Resident Vision**: **CONFIRMED.** Qwen 3.5 4B running in 4.7GB VRAM with ~27-40s prefill.
*   **Dual-Core Residency**: **VERIFIED.** Logic (DeepSeek-R1 14B @ 51 tok/s) and Vision (Qwen 3.5 4B) running simultaneously in 16GB VRAM.
*   **Triton 3.5.1 + PyTorch 2.9.1**: Stable native pairing for GFX1201.
*   **Unsloth 4-bit Native**: Works perfectly once vLLM/CUDA dependency checks are bypassed.

## 🟡 2. THE "YELLOW ZONE" (Functional Workarounds)
*   **Prefill Latency**: Currently 27-40s. Bottleneck identified in Triton prefill kernels; target is <5s.
*   **FP8 Hardware Status**: **RESEARCHED.** GFX1201 supports `float8_e4m3fnuz` natively, but Triton 3.5.1 lacks intrinsic legalization. 10x slowdown due to software emulation.
*   **Frankenstein Build**: Setup uses 24.04 container libraries on 22.04 host. OS migration to 24.04 planned.

## 🔴 3. THE "RED ZONE" (Confirmed Broken)
*   **Native FP8 MatMul**: PyTorch `addmm` and Triton kernels currently fail legalization/intrinsic mapping for GFX1201.
*   **Native pip install causal-conv1d**: Still blocked by hardcoded NVIDIA/NVCC checks.
*   **vLLM Native Linking**: ABI drift in PyTorch Nightly breaks binary extension loading (`getCurrentHIPStream` error).

---

## 🏗️ BUILD REPORT: "POACHERS SPECIAL ED"
**Methodology**: Sovereign Extraction & Infiltration
1.  **Liberated** optimized RDNA 4 wheels (Torch/Triton/Apex) from `rocm/vllm-dev:rocm7.2_navi`.
2.  **Poached** internal Triton kernels (`fla`, `causal_conv1d`) directly from container source.
3.  **Engineered** local shims to strip `vllm` and `cuda` dependencies.
4.  **Nuclear Patch** applied to Unsloth to ignore hardware gatekeeping.

**Current Verdict**: The RX 9070 XT is a fully-functional, resident-capable AI workstation for Logic (14B) + Vision (4B) workflows.
### RDNA 4 Training Status\n\n- **Attempt:** Native PyTorch/TRL (Bypassing Unsloth)\n- **Result:** FAILED at Step 88/100.\n- **Error:**  (Error 700)\n- **Conclusion:** The issue is NOT Unsloth. It is a fundamental memory allocator bug () in the core ROCm 7.2 / PyTorch backend for the GFX1201 architecture during the backward pass (Autograd). Training is currently broken at the driver level until AMD releases a patch.

### RDNA 4 Training Status
- **Attempt:** Native PyTorch/TRL (Bypassing Unsloth)
- **Result:** FAILED at Step 88/100.
- **Error:** HIP error 700: an illegal memory access was encountered
- **Conclusion:** The issue is NOT Unsloth. It is a fundamental memory allocator bug (c10 hip backend) in the core ROCm 7.2 / PyTorch backend for the GFX1201 architecture during the backward pass (Autograd). Training is currently broken at the driver level until AMD releases a patch.

### CRITICAL FIX: The "HIP error 700" Wavefront Bug
- **The Symptom:** Any 4-bit or 8-bit quantized training run immediately crashes with  during the backward pass.
- **The Cause:** If the python environment cannot find the  binary in the system PATH, PyTorch/BitsAndBytes defaults to assuming a "Warp Size" of 64 (standard for CDNA data center cards). RDNA 4 (gfx1201) operates on a Wave32 (Warp Size 32) architecture. When the training loop requests 64-thread memory chunks from a 32-thread die, it hits invalid memory addresses and kernel panics.
- **The Solution:** ALWAYS ensure the ROCm bin directory is in the PATH before importing PyTorch:
  ```python
  import os
  os.environ['PATH'] = '/opt/rocm-7.2.0/bin:/opt/rocm/bin:' + os.environ.get('PATH', '')
  import torch
  ```
- **Current Stable Training Path:** 8-bit Quantization (BitsAndBytes) + LoRA +  PATH fix. Note: Training is currently significantly slower than NVIDIA equivalents due to non-fused kernels, but it is 100% stable.


### CRITICAL FIX: The "HIP error 700" Wavefront Bug
- **The Symptom:** Any 4-bit or 8-bit quantized training run immediately crashes with  during the backward pass.
- **The Cause:** If the python environment cannot find the  binary in the system PATH, PyTorch/BitsAndBytes defaults to assuming a "Warp Size" of 64 (standard for CDNA data center cards). RDNA 4 (gfx1201) operates on a Wave32 (Warp Size 32) architecture. When the training loop requests 64-thread memory chunks from a 32-thread die, it hits invalid memory addresses and kernel panics.
- **The Solution:** ALWAYS ensure the ROCm bin directory is in the PATH before importing PyTorch:
  
- **Current Stable Training Path:** 8-bit Quantization (BitsAndBytes) + LoRA +  PATH fix.

### ISA Reference & Custom Triton Kernel Strategy
- **The "Triton Pivot":** If a PyTorch function or library is hardcoded to fail on RDNA 4 (Wave32), the permanent end-around is to write a custom Triton kernel. Triton JIT-compiles Python directly into `gfx1201` (RDNA 4) machine instructions, bypassing broken C++ libraries.
- **Reference Material:** To write low-level Triton/AMDGCN kernels, you need the official AMD Instruction Set Architecture (ISA) Reference Guides.
    - **Primary Source:** Search [GPUOpen](https://gpuopen.com/amd-gpu-architecture-programming-documentation/) for the "RDNA4 Instruction Set Architecture Reference Guide" and "RDNA3 Instruction Set Architecture Reference Guide".
    - **LLVM Docs:** [LLVM AMDGPU Usage](https://llvm.org/docs/AMDGPUUsage.html) is critical for understanding compiler mapping and specific `gfx1201` intrinsics.

### THE "FULL LORA" REALITY CHECK (March 2026)
- **The NVIDIA Equivalent:** A 16GB NVIDIA card (like the 5070 Ti) can comfortably train all linear layers () of a 7B model using 4-bit or 8-bit quantization.
- **The RDNA 4 Reality:** As of ROCm 7.2 and bitsandbytes 0.46+, targeting the MLP layers (, , ) on a consumer  card results in a near-guaranteed **** during the backward pass (usually between iterations 10-30). 
- **The Root Cause:** The backward pass/outlier detection kernels for these specific MLP projections are still fundamentally broken for Wave32 architectures. They attempt to write to 64-bit execution masks, causing a hardware panic.
- **The Only Stable Path Today:** You MUST restrict your LoRA targets to **Attention layers only** (, , , ). This limits the depth of the fine-tune compared to an NVIDIA card, but it is the only way to complete a multi-epoch training run without a crash.


### THE "FULL LORA" REALITY CHECK (March 2026)
- **The NVIDIA Equivalent:** A 16GB NVIDIA card (like the 5070 Ti) can comfortably train all linear layers () of a 7B model using 4-bit or 8-bit quantization.
- **The RDNA 4 Reality:** As of ROCm 7.2 and bitsandbytes 0.46+, targeting the MLP layers (, , ) on a consumer  card results in a near-guaranteed **** during the backward pass (usually between iterations 10-30). 
- **The Root Cause:** The backward pass/outlier detection kernels for these specific MLP projections are still fundamentally broken for Wave32 architectures. They attempt to write to 64-bit execution masks, causing a hardware panic.
- **The Only Stable Path Today:** You MUST restrict your LoRA targets to **Attention layers only** (, , , ). This limits the "depth" of the fine-tune compared to an NVIDIA card, but it is the only way to complete a multi-epoch training run without a crash.

### The bitsandbytes Compile Wall (March 2026)
- **The Issue:** Attempting to compile  from source on Ubuntu 24.04 to fix the RDNA 4 block size bug currently fails silently. CMake consistently fails to locate the ROCm compiler paths, even when explicitly passed via  or , resulting in a CPU-only wheel () being built and installed.
- **The Cause:** This is likely due to deeply nested hardcoded paths or a CMake detection module bug within the  setup files that conflict with the standard ROCm 7.2 installation structure on bare metal Ubuntu.
- **The Workaround:** Until pre-built  wheels for  are officially released or the CMake files are patched to respect user-provided compiler paths, **Full-Layer 8-bit/4-bit LoRA (including MLP layers) is practically impossible on consumer RDNA 4.**
- **The Sovereign Default:** You must fall back to the "Safe 4" modules (, , , ) for fine-tuning.

### THE "LIFEBOAT" PROTOCOL: Docker Sovereignty
- **The Concept:** As long as we retain a copy of a fully functional, RDNA 4-optimized Docker container (), we are immune to upstream ecosystem breakage. The container is a perfectly preserved, self-contained "Lifeboat" that holds the working compilers, patched libraries, and system paths.
- **The Strategy:** While Bare-Metal execution is preferred for the Sovereign Engine's daily operations, the Docker container serves as the ultimate fallback for complex tasks (like Full-Layer LoRA compilation) that rely on rapidly changing or broken dependencies.
- **Retention Mandate:** NEVER delete the  or  images from the local Docker cache unless they are immediately being replaced by a verified, working newer version. 
