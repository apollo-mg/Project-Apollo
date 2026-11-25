# NOTE: CachyOS's build of hip-runtime-amd 10.1 segfaults creating a second HIP stream on gfx1201; Arch's build of the same version does not (2026-11-24)

**Symptom:** after the 11-24 update (ROCm 7.2.4 -> 10.1), every llama.cpp HIP build on the desktop (RX 9070 XT, gfx1201,
kernel 7.3.5-2-cachyos) crashed at context creation; gdb: `hipStreamCreateWithFlags` -> SIGSEGV inside
`libamdhip64.so.7`; the kernel logs a general protection fault at `libamdhip64.so.7.16.0-4f6d503` +0x74d5b8 for every
crash. Builds made with the 10.1 toolchain run fine on the 7.2.4 runtime, so the compiler is not at fault.

**Minimal repro** (`hip_stream_repro.cpp`, no llama.cpp): hipGetDeviceCount, hipSetDevice(0), hipMalloc 1 MiB,
hipStreamCreateWithFlags(NonBlocking), hipStreamCreate, hipStreamSynchronize. Built with `/opt/rocm/bin/hipcc
--offload-arch=gfx1201`, run 20 times per runtime (only `libamdhip64` / `libhsa-runtime64` swapped via `LD_LIBRARY_PATH`):

| libamdhip64 | libhsa-runtime64 | crashes of 20 |
|---|---|---|
| CachyOS `hip-runtime-amd 10.1-2.1` (cachyos-extra-v3; sha256 `58eb452cde2a3903...`) | CachyOS `hsa-rocr 10.1-1.1` | **17** (all at the second stream) |
| CachyOS 10.1-2.1 | Arch `hsa-rocr 10.1-1` | **10** |
| Arch `hip-runtime-amd 10.1-2` (extra; sha256 `4c34b4b5d6abd9c7...`, signature good) | CachyOS 10.1-1.1 | **0** |
| Arch 10.1-2 | Arch 10.1-1 | **0** |
| private ROCm 7.2.4 (unpacked from pacman's cache) | 7.2.4 | **0** |

So the fault shows in CachyOS's build of the 10.1 HIP runtime, not in Arch's build of the same source (the cause is upstream; see the update below). Both libraries
report GCC 16.2.1 20260810 in `.comment`; CachyOS's file name carries a source hash (`7.16.0-4f6d503`) where Arch's
carries `7.16.0-0000000`, so the two may differ in source revision as well as flags. With Arch's `libamdhip64` swapped in
(`tools/rocm101arch.sh`), the mainline `33aeb17f8` build ran three `llama-perplexity` passes cleanly on ROCm 10.1, with
the same perplexity as on the 7.2.4 runtime (8.3434).

**Searched first (11-24, briefly):** no matching report in ROCm/rocm-systems issues or on the web.

**Reported 2026-11-24 by Mark:** [CachyOS/CachyOS-PKGBUILDS#2196](https://github.com/CachyOS/CachyOS-PKGBUILDS/issues/2196) (package `hip-runtime-amd 10.1-2.1`, cachyos-extra-v3). Re-test the system runtime with `hip_stream_repro.cpp` after any update of that package.

## Update, same evening: already known, and the root cause is upstream (2026-11-24)

#2196 was closed as a duplicate. Earlier reports on CachyOS: #2137 (open, 11-16; the znver4 build, AVX-512 alignment
crash, "Arch generic works") and #2143 (11-17, the same SIGSEGV on a Radeon AI PRO R9700, gfx1201; closed as a duplicate
11-24), with confirmations on gfx1030, gfx1102, gfx1103 and gfx1151. A commenter on #2143 traced it to an **upstream clr
bug, open at AMD**: ROCm/rocm-systems#11256 (opened 2026-09-04, "hipStreamCreate #GPs in VirtualGPU ctor when built with
-march=znver1 (over-aligned new hidden)") and #14003 (2026-10-22, znver4). As described there, `amd::ReferenceCountedObject`
declares a class-scope `operator new(size_t)` without an `align_val_t` overload, so `new roc::VirtualGPU` (a class with
`alignas(64)` members) gets ordinary 16-byte heap storage; builds tuned for newer CPUs emit aligned 32/64-byte vector
stores that fault when that storage happens to be misaligned. Arch's generic build does not emit them, so it survives.
This fits what we measured: a crash rate below 100 % (17 of 20; alignment depends on the heap address), and a clean run
whenever Arch's library is swapped in.

**Corrected reading:** the defect is AMD's (undefined behaviour in clr, known upstream since September and still open);
CachyOS's CPU-optimised build is what exposes it. The workaround stands: Arch's `libamdhip64` (`tools/rocm101arch.sh`).
