# Result -- SCALE's cuModuleGetFunction succeeds on symbols that do not exist, in 1.7.3

**Run 2026-09-17 on the RX 9070 XT (gfx1201, 16 GB), SCALE 1.7.3, ROCm 7.2.4, CachyOS.**
Prereg: `PREREG_SCALE_MODULEGETFN.md` (predictions committed before the probe was built).
Data: `modulegetfn_probe.log`. Probe: `tools/scale-probe/modulegetfn_probe.cu` +
`probe_kernel.cu`.

## Headline

**Both #1119 defects are confirmed unfixed in SCALE 1.7.3.** This one reproduces exactly as
Atlas logged it on 1.7.1:

```
cuModuleGetFunction [absent]  -> 0 (CUDA_SUCCESS)   handle 0x55e213f9a5a0
cuLaunchKernel      [absent]  -> 200 (CUDA_ERROR_INVALID_IMAGE)
```

NVIDIA's driver returns `CUDA_ERROR_NOT_FOUND` (500) at lookup. SCALE returns success,
hands back a non-NULL handle, and defers the failure to launch.

Atlas's ELF symbol-table validation in PR #1107 must stay, alongside the sysfs memory
workaround from the companion receipt.

## What was measured

| step | result |
|---|---|
| `cuModuleLoad` | `CUDA_SUCCESS` |
| control: lookup of `probe_real_kernel` (present) | `CUDA_SUCCESS`, handle `0x55e213fb15b0` |
| control: launch + synchronize | both `CUDA_SUCCESS` |
| **lookup of an absent symbol** | **`CUDA_SUCCESS` (0)** |
| **handle returned for the absent symbol** | **`0x55e213f9a5a0`, non-NULL** |
| **launch on that handle** | **`CUDA_ERROR_INVALID_IMAGE` (200)** |
| `cuCtxSynchronize` after the failed launch | `CUDA_SUCCESS` (context survives) |

The absent-symbol handle is a distinct heap address from the valid one, not a recycled
pointer. SCALE appears to allocate a function object and return it without ever confirming
the symbol resolves.

## Exploratory (not preregistered): the defect is specific to function lookup

`cuModuleGetGlobal` on an absent global **fails at lookup**, returning 200
(`CUDA_ERROR_INVALID_IMAGE`) with a NULL pointer and size 0.

So SCALE's two module-lookup paths do not behave alike: the global path validates before
returning, the function path does not. That is a useful narrowing for the upstream report --
it points at `cuModuleGetFunction` specifically rather than at a general "module lookups do
not check the symbol table" design choice, and it means there is already correct behaviour
in the same module to model the fix on.

Caveat worth stating: `cuModuleGetGlobal` is also not NVIDIA-correct. It returns
`CUDA_ERROR_INVALID_IMAGE` where NVIDIA returns `CUDA_ERROR_NOT_FOUND`. It gets the *timing*
right (fail at lookup) and the *error code* wrong. Two different severities: wrong code is
cosmetic, wrong timing is not.

## Prediction scorecard

| id | prediction | result |
|---|---|---|
| **P-C1** | control: present symbol looks up and launches cleanly | **CONFIRMED** |
| **P-C2** | **THE FORK.** absent lookup returns `CUDA_SUCCESS`, not `CUDA_ERROR_NOT_FOUND` | **CONFIRMED** -- returned 0 |
| **P-C3** | the absent handle is non-NULL | **CONFIRMED** -- `0x55e213f9a5a0` |
| **P-C4** | launch fails with `CUDA_ERROR_INVALID_IMAGE` (200) | **CONFIRMED** -- exactly 200 |

Four for four, and no instrument defect this time. Low difficulty: Atlas had already
published the expected trace, so these predictions were reading their log and confirming it
on a different board and a newer SCALE. The informative part is the version, not the
prediction.

## Why this matters for Atlas specifically

Atlas dispatches from a filesystem kernel registry keyed `kernels/<hw>/<model>/<quant>/`.
Under this defect, "no kernel was built for this hardware and model and quant" -- the
expected state on a new target like gfx1201 -- does not surface as a named lookup failure.
It surfaces later as `CUDA_ERROR_INVALID_IMAGE` from a launch, with no symbol name attached.

On a mature target that is a nuisance. During a bring-up, where missing kernels are the
normal case rather than the exception, it is the difference between an error that tells you
which kernel is missing and one that does not. That is why their ELF-validation workaround
exists, and it is the argument for why the upstream fix is worth Spectral's time rather than
being permanently papered over downstream.

## Build and run

SCALE's `nvcc` does not accept `-fatbin` (it is clang underneath; the flag is unknown). The
device object is produced with `--cuda-device-only -c`, which emits an AMD GPU ELF
relocatable, and `cuModuleLoad` accepts that directly -- the control kernel loads, launches
and synchronizes from it.

Both source files need `-U_GNU_SOURCE` for the glibc C23 collision documented in
`RESULT_SCALE_MEMINFO.md`.

```
nvcc -U_GNU_SOURCE --cuda-device-only -c -o probe_kernel.o probe_kernel.cu
nvcc -U_GNU_SOURCE -o modulegetfn_probe modulegetfn_probe.cu -lcuda
LD_LIBRARY_PATH=$SCALE/targets/gfx1201/lib ./modulegetfn_probe probe_kernel.o
```

## Environment

Identical to `RESULT_SCALE_MEMINFO.md`: RX 9070 XT / gfx1201, SCALE 1.7.3 (sha256
`869afb15e6a947c7966cdf9408633eab6390b21ddae3755538eba3127c6871da`), ROCm 7.2.4, CachyOS
kernel 7.2.3-1-cachyos, glibc 2.44, gcc 16.2.1.

## Status of #1119 after both probes

| defect | 1.7.1 (Atlas, R9700 32 GB) | 1.7.3 (here, RX 9070 XT 16 GB) |
|---|---|---|
| `cudaMemGetInfo` 4x over-charge | reported | **reproduced**, exactly 4.00x, invariant across chunk size |
| `cuModuleGetFunction` false success | reported | **reproduced**, identical trace |

Neither is fixed. Both workarounds stay. Three items are now ready to report upstream to
Spectral: the two above plus the glibc C23 compile failure, which is unrelated to either and
blocks building on any modern-glibc distro.
