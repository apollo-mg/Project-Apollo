# NOTE: the desktop's ROCm 10.1 update breaks every existing llama.cpp ROCm build; a private ROCm 7.2.4 restores them byte for byte (2026-11-24)

**What changed:** a CachyOS update (2026-11-24 13:08, Mark) moved the system ROCm from 7.2.4 to 10.1 (rocm-core,
hip-runtime-amd, hsa-rocr, comgr, rocm-llvm, rocm-device-libs, rocblas, hipblas, rocsolver, rocsparse, rocprim,
roctracer, rocprofiler-register, rocminfo, rocm-smi-lib) and the kernel from 7.3.3 to 7.3.5. The shared-library names did
not change, so the binaries still start.

**Measured:** two stored desktop arms, replayed on their own binaries, cards and flags (`replay_rocm10.sh`):
- **System ROCm 10.1:** both servers segfault (exit 139) while uploading weights to the GPU (`raw/server_*_R10.log`).
  `rocminfo` sees the card, and PyTorch (bundling ROCm 7.2) runs a GPU matmul, so the driver is healthy: it is the
  7.2.4-built binaries on the 10.1 runtime.
- **The 7.2.4 packages from pacman's cache, unpacked into a private tree** (`/mnt/TG_2TB/AI/rocm-7.2.4`, 9.2 GB; nothing
  installed system-wide) and selected with `LD_LIBRARY_PATH` / `ROCBLAS_TENSILE_LIBPATH` (`tools/rocm724.sh`):
  **FZ_BASE (Granite 4.1 3B, buun 38ada0e1b) 240 of 240 answers identical to 11-23; Q35R (Qwen3.5-9B, PR 32588
  4bc61eed7) 240 of 240 identical.** The new kernel does not move them.

**What to do:** run any desktop ROCm binary built before 11-24 through `tools/rocm724.sh` (the frozen AbstentionBench
judge on f74e2fa included). Whether a fresh build against ROCm 10.1 works on gfx1201 is untested; the three-stack drift
test will find out.
