# Sovereign Engine Build Log: PyTorch 2.4.0 on RDNA 4 (GFX1201)
**Hardware:** AMD RX 9070 XT | **OS:** Ubuntu 22.04 | **ROCm:** 7.2

This log documents the manual patches and "tribal knowledge" required to compile a bare-metal PyTorch engine for RDNA 4, bypassing the need for official AMD Docker images.

---

## 🛠️ Infrastructure Setup
- **Disk I/O:** Do NOT build on NTFS partitions. Git and the compiler will core dump due to filename case-sensitivity and locking issues.
  - **Fix:** Create a dedicated `ext4` partition (e.g., `/media/mark/AI_Fast`).
- **Disk Space:** The PyTorch source + submodules + build artifacts require ~60GB.

## 🏁 The Build hurdles & Patches

### 1. The Missing "Hipify" Step
PyTorch source is CUDA-native. Even with `USE_ROCM=1`, the build often fails to find HIP headers if the codebase hasn't been translated.
- **Fix:** Manually run the AMD build script before starting `setup.py`:
  ```bash
  python3 tools/amd_build/build_amd.py
  ```

### 2. Protobuf CMake Version Conflict
The internal `protobuf` submodule may request a CMake version (3.1.3) that newer ROCm-based CMake versions consider "too old" or deprecated.
- **Fix:** Patch `third_party/protobuf/cmake/CMakeLists.txt`:
  ```bash
  sed -i 's/cmake_minimum_required(VERSION 3.1.3)/cmake_minimum_required(VERSION 3.5)/' third_party/protobuf/cmake/CMakeLists.txt
  ```

### 3. Asmjit Nontrivial Memcall Errors
Newer `amdclang++` versions treat `memcpy` on non-trivial types as an error. This halts the build in the `fbgemm` submodule.
- **Fix:** Add `-Wno-error=nontrivial-memcall` to your `CXXFLAGS`.

### 4. Libnop Template Syntax Error (The "Modern Compiler" Trap)
Newer C++ standards (used in ROCm 7.2's clang) require explicit template arguments for certain calls that were previously implicit.
- **File:** `third_party/tensorpipe/third_party/libnop/include/nop/types/variant.h`
- **Error:** `a template argument list is expected after a name prefixed by the template keyword`
- **Fix:** Provide explicit template arguments for `Construct` and `Assign`.
- **Patched Lines:**
  - Line 241: `index_ = value_.template Construct<Args...>(std::forward<Args>(args)...);`
  - Line 258: `if (!value_.template Assign<T, U>(TypeTag<T>{}, index_, std::forward<U>(value))) {`
  - Line 265: `if (!value_.template Assign<T>(index_, std::forward<T>(value))) {`

### 5. Ninja "Dirty Manifest" Loop
If the build is interrupted or restarted frequently, Ninja may get stuck in a "manifest still dirty after 100 tries" loop due to clock skew or generated file timestamps.
- **Fix:** Deep clean the cache without losing object files:
  ```bash
  rm -f build/CMakeCache.txt build/build.ninja
  ```

### 6. The Triton "Modern Compiler Strictness" Gauntlet
The `aotriton` submodule fails extensively under ROCm 7.2's `amdclang++` due to the `-Werror` flag turning minor stylistic C/C++ deprecations into fatal build crashes.
1. **Deprecated Declarations (`std::get_temporary_buffer`):** Fails inside Triton's LLVM passes.
2. **Pybind11 Literal Operator (`operator"" _s`):** C++11 literal operators no longer allow a space before the suffix.
3. **Missing C Headers (`stdbool.h`):** The Python extension compiler generates C code (`hip.c` and `cuda.c`) using the `bool` keyword without importing `<stdbool.h>`, resulting in a silent `AttributeError: 'NoneType' object has no attribute 'add_stages'` crash when the PyTorch setup script swallows the `gcc` error.
- **Fix:** These errors must be suppressed dynamically inside Triton's isolated CMake submodules and Python scripts:
  - Add `-Wno-deprecated-declarations -Wno-deprecated-literal-operator` to `build/aotriton/src/third_party/triton/CMakeLists.txt` and `python/setup.py`
  - Inject `#include <stdbool.h>` into `build/aotriton/src/third_party/triton/python/triton/runtime/backends/hip.c`
  *(Note to upstream: Triton's `hip.c` and `cuda.c` wrappers must explicitly include `<stdbool.h>` for strict standard C compilers).*

---

## 🚀 The Final Build Command
```bash
export PYTORCH_ROCM_ARCH="gfx1201"
export USE_ROCM=1
export ROCM_PATH="/opt/rocm"
export HIP_PATH="/opt/rocm"
export CXX="/opt/rocm/llvm/bin/amdclang++"
export CC="/opt/rocm/llvm/bin/amdclang"
export CXXFLAGS="-Wno-error=nontrivial-memcall -Wno-error -Wno-missing-template-arg-list-after-template-kw -Wno-deprecated-declarations -Wno-deprecated-literal-operator"
export CFLAGS="-Wno-error=nontrivial-memcall -Wno-error"
export MAX_JOBS=8  # Throttle to prevent AMDGPU driver / OOM crashes
export CMAKE_POLICY_VERSION_MINIMUM=3.5
export CMAKE_PREFIX_PATH="/opt/rocm:/opt/rocm/lib/cmake/hipblas-common:/opt/rocm/lib/cmake/hipblaslt"

python3 setup.py bdist_wheel
```
### 7. Intel-specific FBGEMM & Test Suite Overhead
On non-Intel CPUs (or systems where OpenMP linking is strictly enforced by modern compilers), the `fbgemm` module and the PyTorch test suite can fail to link due to missing `__kmpc_barrier` symbols.
- **Fix:** Disable these non-critical components to speed up the build and ensure successful linking:
  ```bash
  export USE_FBGEMM=0
  export USE_KINETO=0
  export BUILD_TEST=0
  ```

### 8. ROCm/HIP Constant Expression Errors (GFX1201 Specific)
Modern Clang (22+) in ROCm 7.2 may fail to evaluate certain HIP macros (like `warpSize` via `C10_WARP_SIZE`) as constant expressions at compile-time, which is required for `__shared__` memory array sizes.
- **Files:** `aten/src/ATen/native/hip/block_reduce.cuh`, `aten/src/ATen/native/hip/Normalization.cuh`
- **Fix:** Hardcode the known constant values for these architectures:
  - In `block_reduce.cuh`: Set `kCUDABlockReduceMaxThreads = 1024`.
  - In `Normalization.cuh`: Replace `shared[C10_WARP_SIZE]` with `shared[64]`.

### 9. RDNA 4 Wavefront Synchronization (The "Float2" Solution)
GFX1201 (RDNA 4) defaults to a Wave32 execution model, but certain PyTorch templates assume a constant warp size for shared memory allocation.
- **Fix:** In `c10/macros/Macros.h`, hardcode `C10_WARP_SIZE` to `32`.
- **Template Failure:** The `Float2` struct in `Normalization.cuh` failed to instantiate for BFloat16/Half types due to missing device-qualified constructors and assignment operators.
- **Fix:** Manually injected `__device__` copy constructors and assignment operators into `Normalization.cuh` to ensure the reduction kernels can correctly pipe data through shared memory.

### 10. HipBLASLT ABI Drift (ROCm 7.2.0 Specific)
ROCm 7.2.0 has deprecated certain `hipblas` type definitions in favor of the more unified `hip` types. PyTorch 2.4.0's tunable operator headers were still using the older naming convention, causing a fatal signature mismatch during matrix layout creation.
- **File:** `aten/src/ATen/hip/tunable/GemmHipblaslt.h`
- **Error:** `unknown type name 'hipblasDatatype_t'; did you mean 'hipblasDiagType_t'?`
- **Fix:** Performed a global replacement of `hipblasDatatype_t` with `hipDataType` within the header file. This aligns the PyTorch tunable GEMM operations with the modern ROCm 7.2.0 API.

### 11. Torch Dynamo C/C++ Standard Mismatch
The Torch Dynamo engine contains several `.c` files that are compiled with C++17 flags in certain build configurations, causing a fatal error in ROCm's `amdclang`.
- **Files:** `torch/csrc/dynamo/cpython_defs.c`, `torch/csrc/dynamo/eval_frame.c`
- **Error:** `error: invalid argument '-std=c++17' not allowed with 'C'`
- **Fix:** Renamed both files to `.cpp` and updated `build_variables.bzl` to reflect the new extensions. This allows the compiler to process them using the C++ standard as intended by the build system's flag injection.

### 12. Functorch C/C++ Extension Mismatch
Similar to Torch Dynamo, the `functorch` module contains pure C files that collide with C++ standard flags injected by the ROCm build environment.
- **File:** `functorch/csrc/dim/dim_opcode.c`
- **Fix:** Renamed to `.cpp` and updated `build_variables.bzl`.

### 13. C-Linkage Preservation for Renamed Dynamo Files
When renaming Dynamo/Functorch `.c` files to `.cpp`, the compiler defaults to C++ name mangling, breaking the Python extension's initialization symbols.
- **Fix:** Wrapped the entire contents of the renamed `.cpp` files in `extern "C" { ... }` blocks to preserve C-linkage while allowing C++ standard flags to pass.

### 15. RDNA 4 Kernel Calibration (TunableOp)
After the build is complete, the engine must be calibrated for GFX1201 to avoid sub-optimal generic kernels.
- **Action:** Run the offline tuning sweep to profile all GEMM operations.
- **Command:**
  ```bash
  export PYTORCH_TUNABLEOP_ENABLED=1
  export PYTORCH_TUNABLEOP_TUNING=1
  export PYTORCH_TUNABLEOP_FILENAME="tunableop_results0.csv"
  # Run a heavy workload (e.g., LLM inference or a benchmark script)
  python3 benchmark_llm.py
  ```
- **Verification:** Ensure `tunableop_results0.csv` is populated with kernel IDs and execution times. This file should be committed to the project root or tracked in the "Vault" to prevent re-tuning on every reboot.

### 16. The vLLM C++ PyBind11 Paradox
Building bleeding-edge vLLM directly against the custom PyTorch 2.4.0a0 core results in fatal `ImportError: undefined symbol` crashes (e.g., `_ZNK3c1010TensorImpl15incref_pyobjectEv`). 
- **Cause:** Upstream PyTorch 2.4.0 deprecated and removed several internal Python C-API bindings (like `incref_pyobject` and `MessageLogger`). However, vLLM's `sgl_kernel` and `_C.abi3.so` C++ extensions still hardcode these missing symbols in their `PyBind11` integration layers.
- **Why AMD's Docker Works:** The official `rocm/vllm` Docker image does not use upstream PyTorch. They use a private fork (`github.com/ROCm/pytorch`) and compile vLLM against that specific ABI, which still maintains those legacy C++ bindings.
- **The Sovereign Solution:** To achieve maximum TPS with vLLM on an RX 9070 XT, you must use the official AMD Docker container. Bare-metal vLLM compilation currently requires maintaining an entire fork of the PyTorch C++ API to satisfy vLLM's custom attention kernels.

### 17. The SGLang / torchvision operator conflict
When using HuggingFace `transformers` (and by extension SGLang) natively on the custom PyTorch 2.4 core, importing `AutoProcessor` crashes with `RuntimeError: operator torchvision::nms does not exist`.
- **Cause:** The `torchvision` package installed via standard pip index (even the ROCm version) is compiled against an older PyTorch ABI. When loaded into the same memory space as our custom `libtorch_hip.so`, the C++ operators fail to register.
- **Fix:** `torchvision` must be compiled from source directly against the custom GFX1201 PyTorch core.
  ```bash
  git clone https://github.com/pytorch/vision.git
  cd vision && export FORCE_CUDA=1 && export USE_ROCM=1
  python3 setup.py bdist_wheel
  pip install dist/*.whl
  ```

### 18. The vLLM RDNA 4 FP8 Breakthrough (March 2026)
Successfully achieved high-throughput FP8 inference on the RX 9070 XT (gfx1201) using the specialized Navi-dev Docker image.
- **The "16GB Wall":** Verified that a 9B model in FP8 (12GB weights) leaves zero room for vLLM's KV cache profiling on a 16GB card. 7B models are the "Sovereign Sweet Spot."
- **The Unfused Layer Trap:** Identified that Qwen 3.5 9B FP8 models with separate `gate_proj` and `up_proj` matrices (unfused) fail in the current ROCm vLLM kernels.
- **The Verification Model:** Standardized on `neuralmagic/Qwen2.5-7B-Instruct-FP8-Dynamic`.
- **Benchmark Record:** 198.5 Tokens/Sec (Batch 64), 319.0 Prompt TPS, 100% KV Cache saturation.
- **Golden Image:** \`rocm/vllm-dev:rocm7.2_navi_ubuntu24.04_py3.12_pytorch_2.9_vllm_0.14.0rc0\`

### 19. ComfyUI RDNA 4 Optimization & The 16GB Wall (March 2026)
Successfully optimized the image generation pipeline for the RX 9070 XT using bleeding-edge PyTorch.
- **The Engine:** Standardized on `PyTorch 2.12.0.dev + ROCm 7.2`. Verified native RDNA 4 (gfx1201) hardware handshake.
- **The Flux Equation:** Verified that Flux FP8 (12GB UNet + 4.6GB T5) exceeds 16GB VRAM when pinned.
- **Dynamic Offloading:** Confirmed that `--normalvram` mode is mandatory for Flux on 16GB cards. This allows the T5 encoder to swap to System RAM, freeing the GPU for the DiT sampling phase.
- **Performance:** Verified clocks hitting **3149 MHz** during sustained 1024x1024 sampling passes.
- **Stability:** Patched custom node `requirements.txt` files to prevent automated PyTorch/ROCm overwrites.

### 20. Control Plane Isolation (Pi 5 Bridge)
To eliminate the risk of session loss during hard OOM crashes on the workstation, the Gemini CLI has been migrated to a Raspberry Pi 5.
- **Architecture:** The Pi 5 hosts the CLI and project metadata (Control Plane), while the PC-Ubuntu handles the compute (Data Plane) via SSH.
- **Resilience:** If the workstation crashes, the CLI remains alive on the Pi, preserving chat history and enabling remote recovery.

## [2026-03-09] POACHERS SPECIAL ED: THE BARE-METAL LIBERATION
**Objective**: Establish high-speed vision without Docker or vLLM linkage errors.
**Status**: SUCCESSFUL

### **Engineering Reflection**
Today we proved that the AMD ecosystem has the necessary high-performance kernels for RDNA 4, but they are intentionally or incompetently "walled off" inside specific Docker containers. By treating the Docker image as a "parts bin" rather than a cage, we extracted:
1.  **Golden Wheels**: Pre-compiled PyTorch 2.9 and Triton 3.5 binaries optimized for GFX1201.
2.  **Kernel Source**: Liberated the Triton-based \`fla\` and \`causal_conv1d\` kernels.

### **The "Poachers" Stack**
*   **Host**: Ubuntu 22.04
*   **Venv**: Python 3.12 (Sovereign)
*   **Kernels**: Standing alone, patched to remove all external gatekeeping logic.
*   **Outcome**: Qwen 3.5 4B Vision is now resident at ~4.7GB VRAM. Logic (R1-14B) is resident at ~9.1GB VRAM.

### **Next Mission**
Integrate the "Poachers" Vision Core into the Architect toolset. Target: Autonomous workstation self-diagnostics.
