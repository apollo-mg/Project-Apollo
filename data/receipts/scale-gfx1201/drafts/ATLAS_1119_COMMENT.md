# Draft comment for Avarok-Cybersecurity/atlas issue #1119

ASCII only. Paste target: https://github.com/Avarok-Cybersecurity/atlas/issues/1119

Re-read the thread before posting; this was drafted against the issue as of 2026-09-17 and
assumes no one has already answered the 1.7.3 question.

---

Reproduced both defects on **SCALE 1.7.3** on a different board, so the version question
this issue tracks has an answer: **neither is fixed, and the workarounds in #1107 should
stay.**

Setup: RX 9070 XT (gfx1201, 16 GB consumer, desktop session resident on the card),
ROCm 7.2.4, SCALE 1.7.3. Different from the R9700 reference in every axis except the ISA.

## cudaMemGetInfo

Reproduces at exactly the 4.00x you measured, and it is a clean multiplier rather than fixed
per-allocation bookkeeping. Swept chunk size to check:

| chunk | overhead per alloc | ratio | counter saturates at | requested at that point |
|---|---|---|---|---|
| 4 MiB | 12.00 MiB | 4.00x | alloc #998 | 3.90 GiB |
| 11 MiB | 33.00 MiB | 4.00x | alloc #364 | 3.91 GiB |
| 32 MiB | 96.00 MiB | 4.00x | alloc #126 | 3.94 GiB |

The overhead tracks the request while the ratio holds, and the reachable fraction is flat at
about 24.6% of the board across an 8x range of allocation sizes. Saturation lands where
`4 x requested` reaches the runtime's own reported baseline free.

Two details that may be worth adding to the upstream report:

**The counter pins at a nonzero floor.** On this board it stops at 58,985,472 bytes
(56.25 MiB) rather than reaching zero, and then **337 further allocations succeed** while it
sits there. If you ever automate a regression check for this, gating on `free == 0` will
miss it; gating on "free stopped moving while allocation still succeeds" catches it. I got
this wrong in the first version of my own probe and it reported a clean run on a board that
had been pinned for 337 allocations.

**"No recovery" looks like it is scoped to the process.** I reproduce the in-process figure
(48.5% of baseline free restored after freeing everything), but after the process exits
sysfs returns to its pre-run baseline, so the driver does reclaim it all. That reframes it
as a runtime accounting and caching failure rather than a leak, which are different bugs
with different fixes and will likely get triaged differently at Spectral.

**One thing I could not reconcile.** The "22064, no recovery" figure does not fit a clean 4x
on a 32 GB board, which should saturate near 7.9 GiB requested rather than 21.5 GiB. My best
guess is that 22064 MiB is where the loop was stopped rather than where the counter pinned,
which is exactly what my run would have reported if I had only recorded the endpoint. If
that is right, the two runs agree. If your trace shows the counter still moving past ~8 GiB
then the behaviour genuinely differs by board and that is worth knowing before filing. Happy
to be told I am reading it wrong.

## cuModuleGetFunction

Identical trace to the one in the issue body:

```
cuModuleGetFunction [absent]  -> 0 (CUDA_SUCCESS)   handle 0x55e213f9a5a0
cuLaunchKernel      [absent]  -> 200 (CUDA_ERROR_INVALID_IMAGE)
cuCtxSynchronize              -> 0 (CUDA_SUCCESS)
```

Control with a real symbol in the same module looks up, launches and synchronizes cleanly.
The absent-symbol handle is a distinct heap address from the valid one rather than a
recycled pointer.

**One addition that narrows it:** `cuModuleGetGlobal` on an absent global **does** fail at
lookup, returning 200 with a NULL pointer and size 0. So SCALE's two module lookup paths do
not agree with each other, and the function path is the odd one out. That is a more
specific thing to hand Spectral than "module lookups do not validate," and it means there is
already correct behaviour in the same module to point at.

(`cuModuleGetGlobal` returns `CUDA_ERROR_INVALID_IMAGE` where NVIDIA returns
`CUDA_ERROR_NOT_FOUND`, so it is not fully correct either, but wrong error code is a
different severity than wrong timing.)

## Probes

Two standalone reproducers, SPDX Apache-2.0, needing only SCALE and a GPU. No Atlas build,
no model weights. They match what acceptance criterion 1 asks for, including recorded
output, and I am happy to open a PR putting them under `scripts/scale-probe/` if that is
useful, or just leave them here for whoever files upstream.

One build note for whoever picks this up: `nvcc -fatbin` is rejected as an unknown argument
(it is clang underneath). `--cuda-device-only -c` emits an AMD GPU ELF relocatable and
`cuModuleLoad` takes it directly.

## Unrelated blocker, same toolchain

SCALE 1.7.3 does not compile at all against glibc 2.41 or newer. Its force-included
`builtins.h` declares `__host__ __device__ double rsqrt(double)` and glibc now exposes
`rsqrt`, `cospi`, `rootn` and `powr` as C23 math functions whenever `_GNU_SOURCE` is set,
which clang does automatically for C++ on Linux:

```
error: __host__ function 'rsqrt' cannot overload __host__ __device__ function 'rsqrt'
```

`-U_GNU_SOURCE` works around it but then breaks `<vector>` and `<string>` via `<cwchar>`, so
it only helps for small C-style code. Invisible on Ubuntu 22.04/24.04 and Rocky/RHEL, which
is presumably why it has not come up. It will hit anyone on Arch or Fedora Rawhide. Filing
that with Spectral separately since it has nothing to do with this issue, but flagging it
here in case it explains a failed bring-up report from someone on a rolling distro.
