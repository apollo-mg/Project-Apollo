# Spectral issue 2 of 3 -- ready to paste

**Tracker:** https://github.com/spectral-compute/scale-validation/issues
**Attach:** `scale_bugreport_sanitized.txt`, `modulegetfn_probe.log`. Paste `modulegetfn_probe.cu`
and `probe_kernel.cu` inline in a `<details>` block rather than attaching -- GitHub does not accept
`.cu` as an attachment type. `scale-probe-sources.tar.gz` is the fallback.

---

**Title:** `cuModuleGetFunction returns CUDA_SUCCESS with an unusable handle for symbols the module does not define (gfx1201)`

---

OS: CachyOS (Arch), kernel 7.2.3-1-cachyos, glibc 2.44
SCALE Version: 1.7.3 (tarball, sha256 869afb15e6a947c7966cdf9408633eab6390b21ddae3755538eba3127c6871da)
GPU: AMD Radeon RX 9070 XT, gfx1201, RDNA 4. ROCm 7.2.4.
Description: Looking up a kernel symbol that is not present in a loaded module returns `CUDA_SUCCESS` together with a non-NULL handle. The failure is deferred to launch time, where it surfaces as `CUDA_ERROR_INVALID_IMAGE` with no symbol name attached. NVIDIA's driver returns `CUDA_ERROR_NOT_FOUND` (500) at lookup time.
Steps to Reproduce:
1. `nvcc -U_GNU_SOURCE --cuda-device-only -c -o probe_kernel.o probe_kernel.cu` (see the separate glibc ticket for why `-U_GNU_SOURCE` is needed).
2. `nvcc -U_GNU_SOURCE -o modulegetfn_probe modulegetfn_probe.cu -lcuda`
3. `LD_LIBRARY_PATH=$SCALE/targets/gfx1201/lib ./modulegetfn_probe probe_kernel.o`
4. Observe that the lookup of an absent symbol returns 0 rather than 500.

---

## Observed

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

The handle returned for the absent symbol is a distinct heap address from the valid one rather than
a recycled pointer, which suggests a function object is allocated and returned without the symbol
ever being resolved.

## Narrowing: the two module lookup paths disagree with each other

`cuModuleGetGlobal` on an absent global **does** fail at lookup, returning 200
(`CUDA_ERROR_INVALID_IMAGE`) with a NULL pointer and size 0.

So the global path validates before returning and the function path does not. There is already
correct behaviour in the same module to model a fix on.

Separately and at much lower severity: `cuModuleGetGlobal` returns `CUDA_ERROR_INVALID_IMAGE` where
NVIDIA returns `CUDA_ERROR_NOT_FOUND`. It gets the timing right and the error code wrong. The
function path gets the timing wrong, which is the part that matters.

## Why this is worth fixing rather than working around downstream

Runtimes that dispatch kernels from a registry keyed by hardware, model and quantization encounter
"this kernel was not built for this target" as a routine condition during bring-up on a new
architecture. Under this defect that condition does not surface as a named lookup failure. It
surfaces later as `CUDA_ERROR_INVALID_IMAGE` from a launch, with no indication of which symbol was
missing. On a mature target that is a nuisance; during a port it is the difference between an error
that identifies the missing kernel and one that does not.

The Avarok Atlas project currently carries an ELF symbol-table validation workaround for exactly
this (Avarok-Cybersecurity/atlas PR #1107), which they would like to retire once SCALE validates
at lookup.

## Build note

`nvcc -fatbin` is rejected as an unknown argument. `--cuda-device-only -c` emits an AMD GPU ELF
relocatable and `cuModuleLoad` accepts that directly, which is what the reproducer does.

## Environment disclosure

`scalediag` reports one FAILED check on this machine, covering KFD ioctls for IPC memory and P2P
device memory access, because this box runs the upstream kernel amdgpu driver rather than AMD's
DKMS package and CachyOS is not a supported distro. Full output in the attached
`scale_bugreport.txt`.

That cannot account for this result: the reproducer uses one GPU in one process and exercises
neither IPC nor P2P, and the identical behaviour was reported independently against SCALE 1.7.1 on
Ubuntu 24.04 with ROCm 7.2.0 on a Radeon AI PRO R9700 (Avarok-Cybersecurity/atlas issue #1119),
with the same `0` at lookup and `200` at launch.

Happy to re-run on a DKMS driver or a supported distro if that would help rule it out.
