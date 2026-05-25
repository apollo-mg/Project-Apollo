# 🚀 Sovereign Engine: PyTorch RDNA 4 Build Notes

## Hardware Target
- **GPU:** AMD Radeon RX 9070 XT
- **Arch:** `gfx1201`
- **ROCm Version:** 7.2
- **OS:** Ubuntu 22.04 LTS

## Build Environment
- **Python:** 3.10.12 (venv_apollo)
- **PyTorch Version:** 2.4.0a0+gitd990dad
- **Compilers:** 
  - CC: `/opt/rocm/llvm/bin/amdclang`
  - CXX: `/opt/rocm/llvm/bin/amdclang++`

## Critical Build Flags
\`\`\`bash
export PYTORCH_ROCM_ARCH="gfx1201"
export USE_ROCM=1
export MAX_JOBS=8
export CMAKE_PREFIX_PATH="/opt/rocm:/opt/rocm/lib/cmake/hipblas-common:/opt/rocm/lib/cmake/hipblaslt"
export CXXFLAGS="-Wno-error=nontrivial-memcall -Wno-error -Wno-missing-template-arg-list-after-template-kw -Wno-deprecated-declarations -Wno-deprecated-literal-operator"
export CFLAGS="-Wno-error=nontrivial-memcall -Wno-error"
\`\`\`

## Build Logic (Sovereign Override)
- **MAX_JOBS=8:** Throttled to prevent OOM on 32GB RAM during massive parallel compiles.
- **Triton Fix:** Forced `VLLM_USE_TRITON_FLASH_ATTN=0` in runtime to use CK Flash Attention as Triton was unstable on gfx1201 BF16 legalization.
- **CMake Policy:** Minimum 3.5 forced to bypass version strictness in older ROCm build scripts.

## Artifacts
- Final Wheel: \`/media/mark/AI_Fast/pytorch_source/dist/torch-2.4.0a0+gitd990dad-cp310-cp310-linux_x86_64.whl\`
- Log: \`/media/mark/AI_Fast/pytorch_final_build.log\`
