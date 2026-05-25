# 🚀 The RDNA 4 (RX 9070 XT) PyTorch & vLLM Build Guide

> **⚠️ ALPHA / EXPERIMENTAL RELEASE**
> This guide outlines a "bleeding-edge" bare-metal compilation process for the AMD Radeon RX 9070 XT (GFX1201) using ROCm 7.2. These patches bypass undocumented compiler strictness changes and API mismatches between PyTorch, vLLM, and HuggingFace. It is provided "as-is" for the community. Use at your own risk.

If you own an AMD Radeon RX 9070 XT and want to run native local AI, you cannot use standard PyTorch binaries or Docker containers. You must compile from source against ROCm 7.2 using the `gfx1201` architecture flag.

This guide contains the exact surgical patches required to bypass the bleeding-edge compiler errors.

## Phase 1: PyTorch 2.4.0 Compilation
*Note: You must use PyTorch 2.4.0 to maintain compatibility with stable vLLM releases.*

1. **Clone PyTorch**
   ```bash
   git clone --recursive -b v2.4.0 https://github.com/pytorch/pytorch
   cd pytorch
   ```

2. **The "Wavefront 32" Hardware Patch**
   ROCm 7.2 dynamically evaluates `warpSize`, breaking PyTorch's `constexpr` assertions. You must hardcode it for RDNA 4:
   ```bash
   sed -i 's/constexpr int kCUDABlockReduceMaxThreads = C10_WARP_SIZE \* C10_WARP_SIZE;/constexpr int kCUDABlockReduceMaxThreads = 1024;/' aten/src/ATen/native/hip/block_reduce.cuh
   sed -i 's/shared\[C10_WARP_SIZE\]/shared[64]/g' aten/src/ATen/native/hip/Normalization.cuh
   sed -i 's/#define C10_WARP_SIZE warpSize/#define C10_WARP_SIZE 32/g' c10/macros/Macros.h
   ```

3. **The Triton Deprecation Patch**
   Triton uses `-Werror` which fails on modern ROCm 7.2 deprecation warnings:
   ```bash
   find build/aotriton/src/third_party/triton -name "CMakeLists.txt" -exec sed -i "s/-Werror/-Wno-deprecated-declarations/g" {} +
   sed -i "1i #include <stdbool.h>" build/aotriton/src/third_party/triton/python/triton/runtime/backends/hip.c
   ```

4. **The C/C++ Linkage Patch**
   ROCm 7.2 compiler strictly separates C and C++ standards.
   ```bash
   # In CMakeLists.txt and cmake/Dependencies.cmake, inject:
   # set(CMAKE_PREFIX_PATH "/opt/rocm;/opt/rocm/lib/cmake/hipblas-common;/opt/rocm/lib/cmake/hipblaslt")
   ```

5. **Build**
   ```bash
   export PYTORCH_ROCM_ARCH="gfx1201"
   export USE_ROCM=1
   export ROCM_PATH="/opt/rocm"
   export CXX="/opt/rocm/llvm/bin/amdclang++"
   export CC="/opt/rocm/llvm/bin/amdclang"
   python3 setup.py bdist_wheel
   ```

## Phase 2: vLLM 0.6.2 Compilation

1. **Clone and Patch**
   ```bash
   git clone https://github.com/vllm-project/vllm.git
   cd vllm
   git checkout v0.6.2
   ```

2. **Add GFX1201 to the Whitelist**
   ```bash
   sed -i 's/gfx1100/gfx1100;gfx1201/' CMakeLists.txt
   ```

3. **The vLLM Wavefront Patch**
   ```bash
   sed -i 's/#define WARP_SIZE warpSize/#define WARP_SIZE 32/g' csrc/cuda_compat.h
   sed -i 's/#define WARP_SIZE warpSize/#define WARP_SIZE 32/g' csrc/attention/attention_kernels.cu
   ```

4. **Build**
   *(Ensure you have removed PyTorch dependencies from requirements.txt so it doesn't overwrite your custom build)*
   ```bash
   export PYTORCH_ROCM_ARCH="gfx1201"
   export VLLM_TARGET_DEVICE="rocm"
   python3 setup.py bdist_wheel
   ```

## Phase 3: The HuggingFace RoPE Bug
Newer HuggingFace Transformers libraries break vLLM 0.6.2 when parsing Qwen 2.5 metadata.
You must manually patch `vllm/model_executor/layers/rotary_embedding.py` inside your python site-packages to safely fallback to a standard `RotaryEmbedding` if the `mrope` config fails.

---
**Authored by Project Apollo**