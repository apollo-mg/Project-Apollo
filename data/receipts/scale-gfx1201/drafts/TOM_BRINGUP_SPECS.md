# Reply to Tom -- gfx1201 bring-up target specs

ASCII only. Trim to taste; the constraints section is the part that actually changes a PRD.

---

Here's the full picture so you can scope it properly.

**Hardware**

- AMD Radeon RX 9070 XT, gfx1201, RDNA 4, **16 GB** (15.92 GiB / 17,095,983,104 B)
- Ryzen 7 5700X3D, 8C/16T
- 32 GB system RAM (so limited host headroom for offload/spill)
- 611 GB free NVMe for models
- Single discrete card, and **my desktop session lives on it** (~2.2 GB resident), so figure ~13.7 GiB actually free rather than 15.9

**Software stack as it sits right now**

- CachyOS (Arch), kernel 7.2.3-1-cachyos
- ROCm 7.2.4 (you tested 7.2.0)
- SCALE **1.7.3** installed and working (you were on 1.7.1)
- glibc 2.44, gcc 16.2.1
- **Upstream kernel amdgpu driver, not the AMD DKMS package**

**Three constraints worth knowing before you write anything**

1. **The 27B will not fit.** #1107 has Qwen3.8-27B-NVFP4 at 19.4 GB resident. That is over my
   whole board before the desktop takes its cut. Ornith-9B-NVFP4 fits comfortably. So on this
   card the flagship config isn't a target, and anything you plan should assume the 9B.

2. **SCALE 1.7.3 does not compile against glibc 2.41+ at all**, which is the Spectral ticket I
   filed today. Its force-included `builtins.h` declares `__host__ __device__ double rsqrt(double)`
   and modern glibc exposes rsqrt/cospi/rootn/powr as C23 math whenever `_GNU_SOURCE` is set,
   which clang does automatically for C++. `-U_GNU_SOURCE` gets you compiling but then breaks
   `<vector>` and `<string>` via `<cwchar>`, so it only works for C-style code. **Any build step
   in a PRD needs a real answer here**, or it dies at step one on this box. Might be worth me
   testing in an Ubuntu 24.04 container as a fallback if you'd rather not design around it.

3. **My driver is upstream amdgpu, not DKMS**, so `scalediag` throws a FAILED on KFD ioctls
   (IPC memory and P2P device memory access). Didn't matter for anything single-device I ran
   today, but if the plan touches multi-GPU or IPC paths, that's a known hole. I can install the
   DKMS package if it's in the way.

**Open question I hit and couldn't answer**

The kernel registry keys on `kernels/<hw>/<model>/<quant>/`. If the hw key is `r9700` rather than
`gfx1201`, my card presumably needs a directory or alias entry before anything loads. The ISA is
identical so the kernels should be bit-compatible, but I don't know whether that's a one-line
addition or something with more to it. That's probably the first thing to settle.

**What I already confirmed today** (so you don't plan around it)

Both #1119 defects still reproduce on 1.7.3: `cudaMemGetInfo` at exactly 4.00x, and
`cuModuleGetFunction` returning success for absent symbols. Your workarounds in #1107 need to stay.
Worth knowing that the memory one caps honest capacity reporting at about 3.9 GiB on a 16 GB board,
because the ratio is a flat multiplier rather than fixed overhead. So anything sizing allocations
off `cudaMemGetInfo` will badly misjudge this card specifically.

**Practical notes**

It's hot here so the P100 boxes are suspended most of the time, but the 9070 XT is in my daily
driver and always up. I can turn work around same-day most days. Happy to run whatever you write,
and happy to just be the hands if you'd rather drive.
