# Drafts for Spectral Compute (SCALE)

Three independent items. Each block below is self-contained and can be filed separately
(Discord or hello@spectralcompute.co.uk). ASCII only.

Shared environment line, used by all three:

```
SCALE 1.7.3 (tarball, sha256 869afb15e6a947c7966cdf9408633eab6390b21ddae3755538eba3127c6871da)
GPU:    AMD Radeon RX 9070 XT, gfx1201, RDNA 4, 15.92 GiB
ROCm:   7.2.4
OS:     CachyOS (Arch), kernel 7.2.3-1-cachyos, glibc 2.44, gcc 16.2.1
Note:   a desktop session is resident on the card (~2.6 GB)
```

---

## ITEM 1 -- cudaMemGetInfo charges 4x the requested bytes, then saturates

**Summary**

On gfx1201, `cudaMemGetInfo` decrements its free counter by exactly 4x the bytes actually
requested. The counter reaches a nonzero floor and stops moving entirely, while `cudaMalloc`
continues to succeed for hundreds more allocations. The kernel driver's own accounting
(amdgpu sysfs `mem_info_vram_used`) is correct throughout, so the discrepancy is inside the
SCALE runtime.

**Measurement**

Allocate fixed-size chunks in a loop; at each step compare the runtime's reported free
against sysfs ground truth and against cumulative bytes requested.

| chunk | charged per alloc | overhead per alloc | ratio | counter saturates at | requested at that point |
|---|---|---|---|---|---|
| 4 MiB | 16.00 MiB | 12.00 MiB | 4.00x | alloc #998 | 3.90 GiB |
| 11 MiB | 44.00 MiB | 33.00 MiB | 4.00x | alloc #364 | 3.91 GiB |
| 32 MiB | 128.00 MiB | 96.00 MiB | 4.00x | alloc #126 | 3.94 GiB |

The overhead scales with the request while the ratio stays fixed, so this is a multiplier
and not a fixed per-allocation bookkeeping cost. Saturation occurs where
`4 x requested` reaches the runtime's own reported baseline free (15.625 GiB / 4 = 3.91 GiB),
consistently across all three chunk sizes.

At the 11 MiB saturation point the counter pins at 58,985,472 bytes (56.25 MiB) and never
reaches zero, yet **337 further allocations succeed** while it sits there. sysfs reported
9.34 GiB genuinely free at that moment.

The practical effect: on this 16 GB board only about 3.9 GiB can be allocated before
`cudaMemGetInfo` stops being usable for capacity decisions. Because the ratio is a constant
multiplier, the same proportion should hold on larger boards.

**Recovery**

After freeing all allocations, the runtime restores only 48.5% of the baseline free value
within the process lifetime. After the process exits, sysfs returns to its pre-run baseline,
so the driver does reclaim everything. This looks like an accounting and caching failure in
the runtime rather than a leak, which may help narrow it.

**Possibly separate, same call**

At rest with no allocations outstanding, `cudaMemGetInfo` reports total as the full 15.92 GiB
board and free as 15.625 GiB, implying 0.32 GB in use, while sysfs reports 2.45 GB in use by
the desktop session. The free counter appears not to account for other processes'
allocations at all. This may be a distinct defect from the 4x charge above.

**Cosmetic, noticed in passing**

`scaleinfo` reports constant memory size as 2147483647 B, which is INT_MAX rather than a
real quantity.

**Reproducer**

Standalone, needs only SCALE and a GPU. No inference stack or model weights.
Attach `meminfo_probe.cu` (SPDX Apache-2.0). Build and run:

```
nvcc -U_GNU_SOURCE -o meminfo_probe meminfo_probe.cu      # see ITEM 3 for the flag
LD_LIBRARY_PATH=$SCALE/targets/gfx1201/lib ./meminfo_probe 11 700 out.csv
```

It prints the per-allocation comparison and writes a CSV with requested bytes, reported
free, sysfs used, and the charge ratio at every step.

---

## ITEM 2 -- cuModuleGetFunction returns CUDA_SUCCESS for symbols that do not exist

**Summary**

Looking up a kernel symbol that is not present in a loaded module returns `CUDA_SUCCESS`
with a non-NULL handle. The failure is deferred to launch time. NVIDIA's driver returns
`CUDA_ERROR_NOT_FOUND` (500) at lookup.

**Observed**

```
cuModuleLoad                                   -> 0 (CUDA_SUCCESS)

control, symbol present in the module:
  cuModuleGetFunction [probe_real_kernel]      -> 0 (CUDA_SUCCESS)  handle 0x55e213fb15b0
  cuLaunchKernel                               -> 0 (CUDA_SUCCESS)
  cuCtxSynchronize                             -> 0 (CUDA_SUCCESS)

symbol absent from the module:
  cuModuleGetFunction [definitely_not_a_...]   -> 0 (CUDA_SUCCESS)  handle 0x55e213f9a5a0
  cuLaunchKernel                               -> 200 (CUDA_ERROR_INVALID_IMAGE)
  cuCtxSynchronize                             -> 0 (CUDA_SUCCESS)
```

The handle returned for the absent symbol is a distinct heap address from the valid one, not
a recycled pointer, which suggests a function object is allocated and returned without the
symbol ever being resolved.

**Narrowing: the two module lookup paths disagree**

`cuModuleGetGlobal` on an absent global **does** fail at lookup, returning 200
(`CUDA_ERROR_INVALID_IMAGE`) with a NULL pointer and size 0. So the global path validates
before returning and the function path does not. There is already correct behaviour in the
same module to model the fix on.

Worth noting separately: `cuModuleGetGlobal` returns `CUDA_ERROR_INVALID_IMAGE` where NVIDIA
returns `CUDA_ERROR_NOT_FOUND`. It gets the timing right and the error code wrong. That is a
much lower severity than the function path, which gets the timing wrong.

**Why it matters**

Runtimes that dispatch kernels from a registry keyed by hardware, model and quantization hit
"this kernel was not built for this target" as a normal condition during bring-up on a new
architecture. Under this defect that condition does not surface as a named lookup failure.
It surfaces later as `CUDA_ERROR_INVALID_IMAGE` from a launch with no symbol name attached,
which is materially harder to diagnose.

**Reproducer**

Attach `modulegetfn_probe.cu` and `probe_kernel.cu` (SPDX Apache-2.0).

```
nvcc -U_GNU_SOURCE --cuda-device-only -c -o probe_kernel.o probe_kernel.cu
nvcc -U_GNU_SOURCE -o modulegetfn_probe modulegetfn_probe.cu -lcuda
LD_LIBRARY_PATH=$SCALE/targets/gfx1201/lib ./modulegetfn_probe probe_kernel.o
```

Note: `nvcc -fatbin` is rejected as an unknown argument. `--cuda-device-only -c` emits an
AMD GPU ELF relocatable and `cuModuleLoad` accepts that directly.

---

## ITEM 3 -- SCALE 1.7.3 does not compile against glibc 2.41 or newer

**Summary**

Any compilation fails on a distro shipping a C23-era glibc, because SCALE's force-included
`redscale_impl/builtins.h` collides with glibc's C23 math declarations.

**Error**

```
In file included from <built-in>:1:
In file included from .../redscale_impl/common.h:42:
In file included from .../redscale_impl/builtins.h:705:
In file included from /usr/include/c++/16/cmath:55:
In file included from /usr/include/math.h:450:
/usr/include/bits/mathcalls.h:207:17: error: __host__ function 'rsqrt' cannot overload
    __host__ __device__ function 'rsqrt'
  207 | __MATHCALL_VEC (rsqrt,, (_Mdouble_ __x));
.../redscale_impl/builtins.h:667:26: note: previous declaration is here
  667 | __host__ __DEVICE double rsqrt(double);
```

Also triggers on `cospi`, and the same class covers `rootn` and `powr`.

**Cause**

glibc exposes `rsqrt`, `cospi`, `rootn` and `powr` when
`__GLIBC_USE (IEC_60559_FUNCS_EXT_C23)` is set, which `bits/libc-header-start.h` enables
whenever `__USE_GNU` is defined. clang defines `_GNU_SOURCE` automatically for C++ on Linux,
so the block is always active. SCALE declares the same names as `__host__ __device__`, and
the two declarations cannot overload.

Confirmed this is glibc and not the compiler version: building with `-ccbin g++-15` does not
help, because the declarations live in `/usr/include/bits/mathcalls.h`, which is shared
across GCC versions.

**Workaround and its limits**

`-U_GNU_SOURCE` compiles. It then breaks libstdc++ headers that need `_GNU_SOURCE` for
wide-char support, so `<vector>` and `<string>` fail via `<cwchar>`:

```
/usr/include/c++/16/cwchar:150:11: error: no member named 'fwide' in the global namespace
```

Usable for a small C-style reproducer, not a general answer, since real code cannot give up
the C++ standard library.

**Scope**

Invisible on SCALE's listed platforms (Ubuntu 22.04/24.04, Rocky/RHEL 8/9) because they all
ship older glibc. Affects Arch and derivatives, Fedora Rawhide, and will affect Ubuntu as it
moves forward. Reported here because it is a silent blocker rather than a degraded path:
nothing compiles at all.

**Environment for this item**

glibc 2.44, gcc 16.2.1, clang from the SCALE 1.7.3 tarball.
