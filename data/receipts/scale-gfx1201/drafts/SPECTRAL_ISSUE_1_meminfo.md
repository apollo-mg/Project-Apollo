# Spectral issue 1 of 3 -- ready to paste

**Tracker:** https://github.com/spectral-compute/scale-validation/issues
**Attach:** `scale_bugreport_sanitized.txt`, `meminfo_probe.log`, `meminfo_probe.csv`,
`sweep_4mib.csv`, `sweep_32mib.csv`. Paste `meminfo_probe.cu` inline in a `<details>` block rather
than attaching it -- GitHub does not accept `.cu` as an attachment type, and a reproducer should be
readable without downloading. `scale-probe-sources.tar.gz` is the fallback if you would rather attach.

---

**Title:** `cudaMemGetInfo charges 4.00x the requested bytes on gfx1201 and saturates at a nonzero floor while allocation keeps succeeding`

---

OS: CachyOS (Arch), kernel 7.2.3-1-cachyos, glibc 2.44
SCALE Version: 1.7.3 (tarball, sha256 869afb15e6a947c7966cdf9408633eab6390b21ddae3755538eba3127c6871da)
GPU: AMD Radeon RX 9070 XT, gfx1201, RDNA 4, 15.92 GiB. ROCm 7.2.4. Desktop session resident on the card.
Description: `cudaMemGetInfo` decrements its free counter by exactly 4x the bytes actually requested. The counter then reaches a nonzero floor and stops moving entirely while `cudaMalloc` keeps succeeding for hundreds more allocations. The kernel driver's own accounting is correct throughout, so the discrepancy is inside the SCALE runtime. Freed memory is not credited back within the process lifetime, though it is fully reclaimed when the process exits.
Steps to Reproduce:
1. Build the attached standalone probe: `nvcc -U_GNU_SOURCE -o meminfo_probe meminfo_probe.cu` (the `-U_GNU_SOURCE` is for a separate compile issue, filed as its own ticket).
2. Run `LD_LIBRARY_PATH=$SCALE/targets/gfx1201/lib ./meminfo_probe 11 700 out.csv`.
3. Observe the `charge` column report 4.00x from the first allocation, and the reported free value stop changing at allocation #364 while allocations continue to succeed through #700.

---

## Measurement

Allocate fixed-size chunks in a loop; at each step compare the runtime's reported free against
amdgpu sysfs ground truth and against cumulative bytes requested.

| chunk | charged per alloc | overhead per alloc | ratio | counter saturates at | requested at that point |
|---|---|---|---|---|---|
| 4 MiB | 16.00 MiB | 12.00 MiB | 4.00x | alloc #998 | 3.90 GiB |
| 11 MiB | 44.00 MiB | 33.00 MiB | 4.00x | alloc #364 | 3.91 GiB |
| 32 MiB | 128.00 MiB | 96.00 MiB | 4.00x | alloc #126 | 3.94 GiB |

The overhead scales with the request while the ratio stays fixed, so this is a multiplier rather
than a fixed per-allocation bookkeeping cost. Saturation occurs where `4 x requested` reaches the
runtime's own reported baseline free (15.625 GiB / 4 = 3.91 GiB), consistently at all three sizes.

At the 11 MiB saturation point the counter pins at 58,985,472 bytes (56.25 MiB) and never reaches
zero, yet **337 further allocations succeed** while it sits there. sysfs reported 9.34 GiB
genuinely free at that moment.

Net effect: on this 16 GB board only about 3.9 GiB can be allocated before `cudaMemGetInfo` stops
being usable for capacity decisions. Because the ratio is a constant multiplier, the same
proportion should hold on larger boards.

The failure mode that matters is not that the counter reads low. It is that **the counter
saturates near zero while allocation keeps working**, so any allocator asking "can I fit another
layer?" stops early. A regression check gated on `free == 0` will never fire, because the floor
is nonzero.

## Recovery

After freeing every allocation, the runtime restores only 48.5% of the baseline free value within
the process. After the process exits, sysfs returns to its pre-run baseline, so the driver does
reclaim everything. This reads as an accounting and caching failure in the runtime rather than a
leak, which may help narrow it.

## Possibly a separate defect, same call

At rest with nothing allocated, `cudaMemGetInfo` reports total as the full 15.92 GiB board and free
as 15.625 GiB, implying 0.32 GB in use, while sysfs reports 2.45 GB in use by the desktop session.
The free counter appears not to account for other processes' allocations. This may be independent
of the 4x charge above.

## Cosmetic, noticed in passing

`scaleinfo` reports constant memory size as 2147483647 B, which is INT_MAX rather than a real
quantity.

## Environment disclosure

`scalediag` on this machine reports one FAILED check:

```
Check full-driver
  Some KFD ioctls are not supported. Some features, such as IPC memory and P2P device
  memory access might not work.
   - Make sure you have the AMD-supplied amdgpu DKMS driver installed.
  FAILED
```

This box runs the upstream kernel amdgpu driver rather than AMD's DKMS package, and CachyOS is not
a supported SCALE distro. Disclosing that because it is true, not because it explains the result.
Three reasons it does not:

1. The failed check covers **IPC memory and P2P device memory access**. The measured path here is
   single-device `cudaMalloc` / `cudaMemGetInfo`, one GPU, one process. Neither is exercised.
2. **The same defect was independently measured on a supported configuration.** The Avarok Atlas
   project reported it against SCALE 1.7.1 on Ubuntu 24.04, ROCm 7.2.0, Radeon AI PRO R9700
   (Avarok-Cybersecurity/atlas issue #1119), at 44 MiB charged per 11 MiB requested. That is the
   same 4x, on different hardware, a different distro, a different driver and an older SCALE.
3. On this machine the **kernel driver's accounting is correct throughout** -- amdgpu sysfs
   `mem_info_vram_used` tracks the requested bytes to within rounding at every step. Only SCALE's
   userspace counter diverges. If the driver were the cause, the driver-side number would be the
   wrong one.

Happy to re-run on a DKMS driver or a supported distro if that would help rule it out.
