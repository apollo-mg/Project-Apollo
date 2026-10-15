# Recheck -- SCALE 1.7.4 on gfx1201: the 4x cudaMemGetInfo charge and the glibc C23 collision are fixed; GetFunction and dropped globals are not

**2026-10-14.** SCALE 1.7.4 (released 2026-10-08) against the four SCALE defects measured on the RX 9070 XT
(`RESULT_SCALE_MEMINFO.md`, `RESULT_SCALE_MODULEGETFN.md`, and the dropped-globals finding of 10-07). Every probe was
rebuilt and run with each toolchain, on the same day, card and kernel, so 1.7.3 is a same-day control: anything that
changes between the two columns changed with SCALE, not with the kernel or driver updates since September.

| | finding | 1.7.3 today (control) | 1.7.4 |
|---|---|---|---|
| A | glibc 2.41+ C23 maths collision: nothing compiles without `-U_GNU_SOURCE` | fails (`rsqrt` overload error) | **fixed**: builds with `<vector>`/`<string>`, `rsqrt(4)+cospi(4)` = 1.5 on device |
| B | `cudaMemGetInfo` charges 4.00x the request and pins at a nonzero floor | 4.00x, phantom exhaustion at alloc #133 with 9.56 GiB genuinely free | **fixed**: 1.00x at every step; runtime free tracks sysfs (6.250 GiB requested, 6.250 used) |
| C | `cuModuleGetFunction` returns success and a non-NULL handle for an absent symbol | reproduces | **unchanged**: success, then `CUDA_ERROR_INVALID_IMAGE` (200) at launch |
| D | unreferenced `extern "C" __device__` / `__constant__` globals dropped at `-O3` | reproduces | **unchanged**: `dev_u32`, `const_u32` return 200; `__attribute__((used))` still keeps them |

**What this adds to the earlier receipts:** the version boundary. B was reported upstream
(spectral-compute/scale-validation#67) and is not named in the 1.7.4 release notes, so this probe is the evidence that it
changed. A matches the notes ("Fixed a collision with glibc's C23 maths headers"). C (scale-validation#68) and D are
untouched; D's notes entry ("Fixed a linker bug that led to some device symbols being dropped") is a different bug, or
does not cover this case.

**Not tested here:**
- **B at true exhaustion.** 250 x 32 MiB stops at 7.8 GiB requested, as the 09-17 sweep did. On 1.7.3 that was past the
  phantom floor; on 1.7.4 the card never filled, so the free value at the very end is unmeasured.
- **The FP8 KV decode failure through SCALE (10-07).** The notes list "Fixed conversions from float to fp8 types" under
  PTX support, which may be related; checking it needs a full engine build, not a probe.

## Setup

| | |
|---|---|
| GPU | AMD Radeon RX 9070 XT, gfx1201, desktop resident (~1.6 GB) |
| SCALE 1.7.4 | `scale-1.7.4-amd64.tar.xz` from pkgs.scale-lang.com, 3,398,497,668 bytes, sha256 `02bafec3a9b6aea3548bb78ef258be833298f6c21013973d4474816dbe1987e5` (no published checksum to compare against) |
| SCALE 1.7.3 | the 09-17 tarball, sha256 `869afb15...` (see `RESULT_SCALE_MEMINFO.md`) |
| OS | CachyOS, kernel 7.2.9-2-cachyos |

Probes (all in `tools/scale-probe/`): `glibc_probe.cu` (new), `meminfo_probe.cu 32 250`, `modulegetfn_probe.cu` with
`probe_kernel.cu` built `--cuda-device-only -c`, and `k2.cu` built `-O3 --cuda-device-only -c` read by `probe2.c`
(new). B, C and D are built with `-U_GNU_SOURCE` on both versions so the only variable is SCALE. Outputs per version in
`recheck-1.7.4/` (`recheck_v173.txt`, `recheck_v174.txt`, `meminfo_32mib_*.{log,csv}`).

Other 1.7.4 changes that matter to anything built with it: FP contraction now defaults to nvcc's
`fast-honor-pragmas`, `-prec-div=false` / fast-math now uses approximate division, many single-precision maths
functions changed to meet NVIDIA's error bounds, the occupancy calculator was fixed (it could badly underestimate), and
a race in copies involving pageable host memory was fixed. Outputs compared byte for byte against a 1.7.3 build should
be expected to differ.
