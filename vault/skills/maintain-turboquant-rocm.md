---
name: maintain-turboquant-rocm
description: Update, patch, and compile TheTom's llama-cpp-turboquant engine for AMD RDNA 4 (gfx1201) hardware. Use when you need to pull latest engine updates, apply custom memory leak patches, or rebuild the inference server for ROCm.
---

# Maintaining TurboQuant Engine on AMD RDNA 4

This skill provides the procedure for updating and building TheTom's custom `llama.cpp` fork (`llama-cpp-turboquant`), which is required for stable 64k+ context windows and TurboQuant compression on AMD hardware.

## Prerequisites

- **Hardware**: AMD RX 9070 XT (Architecture: `gfx1201`).
- **OS**: CachyOS (Arch-based).
- **Tooling**: `paru` or `pacman`, `cmake`, `git`, `hipconfig`.
- **Dependencies**: `rocwmma` (optional but recommended for faster attention).

## Update and Build Procedure

Follow these steps to pull the latest engine code and rebuild for the RX 9070 XT.

### 1. Repository Preparation
Navigate to the engine directory and clear any old manual edits to avoid git conflicts.

```bash
cd /mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant
git restore .
git checkout feature/turboquant-kv-cache
git pull origin feature/turboquant-kv-cache
```

### 2. Apply Custom ROCm Patch
Re-apply the custom memory pool bypass patch. This is **critical** to prevent VRAM "creep" and OOM crashes during large context dequantization on ROCm.

```bash
# Verify the patch file exists
ls my_rocm_fattn_fixes.patch

# Apply the patch
git apply my_rocm_fattn_fixes.patch
```

### 3. Configure and Compile
Run CMake with the specific flags for RDNA 4 and TurboQuant optimizations.

```bash
# Set environment variables for the ROCm compiler
HIPCXX="/opt/rocm/lib/llvm/bin/clang"
HIP_PATH="/opt/rocm"

# Configure with CMake
# If rocwmma headers are missing, set -DGGML_HIP_ROCWMMA_FATTN=OFF
cmake -S . -B build \
    -DGGML_HIP=ON \
    -DAMDGPU_TARGETS=gfx1201 \
    -DGGML_HIP_ROCWMMA_FATTN=ON \
    -DCMAKE_BUILD_TYPE=Release

# Build the binaries
cmake --build build --config Release -- -j $(nproc)
```

## Verification

After building, verify the server identifies the GPU and context settings correctly.

1. **Check Log**: Run `start_qwen_36_moe.sh` and look for `n_ctx_slot = 65536`.
2. **Monitor VRAM**: Use `lact` or `rocm-smi` to ensure VRAM usage remains stable during long prompt evaluations.

## Common Pitfalls

- **Patch Application Failure**: If `git apply` fails, the upstream code likely changed the `fattn` kernels. Do NOT proceed without surgically updating the patch logic to bypass the `ggml_cuda_pool_alloc` for HIP.
- **rocWMMA Missing**: If you get a "rocwmma-version.hpp not found" error, install it via `paru -S rocwmma` or disable the flag in CMake.
- **CPU Offloading**: Ensure `-ngl 99` is used in launch scripts. If you see very low TPS (<1), the engine has likely spilled over into system RAM.
