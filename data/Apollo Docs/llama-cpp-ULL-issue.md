# Title: [BUG] Compile Error on RDNA/Wave64 architectures: 64-bit `ULL` suffix missing for warp-sync masks in `fwht.cu` and `mma.cuh`

## Description
When compiling the `llama.cpp` fork on AMD RDNA architectures (e.g. RDNA 3 / RDNA 4 / RX 9070 XT) or any other setup that leverages Wave64 (64-lane warp sizes), the compilation fails with static assertion errors or warnings relating to mask sizes in `fwht.cu` and `mma.cuh`.

The root cause is that a 32-bit integer is being used for warp-sync masks where a 64-bit mask is required for architectures with a warp size of 64. Using `0xffffffff` evaluates to a 32-bit unsigned integer, causing truncation or compiler assertions when passed to synchronization intrinsics that expect a full 64-bit mask on these platforms.

## Fix
To resolve this and ensure compatibility across both Nvidia (Wave32) and AMD (Wave64) hardware, warp-sync masks must explicitly include the `ULL` (Unsigned Long Long) suffix to guarantee they are evaluated as 64-bit integers.

Specifically, any instance of `0xffffffff` used for warp masks in the following files:
- `ggml/src/ggml-cuda/fwht.cu`
- `ggml/src/ggml-cuda/mma.cuh`

Must be updated to `0xffffffffULL`.

## Steps to Reproduce
1. Attempt to build the fork on an AMD GPU utilizing ROCm HIP (e.g., gfx1100 or gfx1201) where the warp size is 64.
2. Observe compiler errors/assertions in `fwht.cu` and `mma.cuh` when processing the 32-bit mask literals.

## Environment
- **Hardware:** AMD RX 9070 XT (gfx1201) / ROCm
- **Impact:** Prevents successful compilation of the backend.