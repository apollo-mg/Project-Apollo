# Result -- SCALE's cudaMemGetInfo on gfx1201: the 4x over-charge survives 1.7.3, and it caps every board at ~24.6% of its VRAM

**Run 2026-09-17 on the RX 9070 XT (gfx1201, 16 GB), SCALE 1.7.3, ROCm 7.2.4, CachyOS.**
Prereg: `PREREG_SCALE_MEMINFO.md` (predictions committed before the run; Amendment 1 capped
the loop for desktop safety, also before the run).
Data: `meminfo_probe.csv`, `sweep_4mib.csv`, `sweep_32mib.csv`, and the matching `.log` files.
Probe: `tools/scale-probe/meminfo_probe.cu`.

## Headline

1. **The `cudaMemGetInfo` defect is NOT fixed in SCALE 1.7.3.** It reproduces at exactly the
   4.00x over-charge Atlas measured on 1.7.1. Their workarounds in PR #1107 must stay.
2. **It is a clean 4x multiplier, not fixed per-allocation bookkeeping.** Measured across an
   8x range of chunk sizes; the overhead scales with the request, the ratio does not move.
3. **The reachable fraction of VRAM is ~24.6%, and it is board-size invariant.** So the harm
   is **absolute, not proportional**: a 16 GB card can reach only **3.9 GiB** before the free
   counter stops telling the truth. That is below what any of Atlas's target models need.

## The measurement

Three chunk sizes, same card, same session:

| chunk | charged per alloc | overhead per alloc | ratio | saturation onset | requested at onset | % of 15.92 GiB |
|---:|---:|---:|---:|---:|---:|---:|
| 4 MiB | 16.00 MiB | 12.00 MiB | **4.00x** | #998 | 3.90 GiB | **24.5%** |
| 11 MiB | 44.00 MiB | 33.00 MiB | **4.00x** | #364 | 3.91 GiB | **24.6%** |
| 32 MiB | 128.00 MiB | 96.00 MiB | **4.00x** | #126 | 3.94 GiB | **24.7%** |

The 11 MiB row reproduces Atlas's "44 MiB per 11 MiB" exactly. The other two rows are the
discriminator: if this were fixed bookkeeping per allocation, the overhead column would be
constant and the fraction would swing. Instead the overhead tracks the request and the
fraction is flat to within 0.2 points. **SCALE charges 4x the requested bytes, period.**

Saturation is exactly where `4 x requested` reaches SCALE's own reported baseline free
(15.625 GiB / 4 = 3.91 GiB). The arithmetic is consistent across all three runs.

Other behaviour, from the 11 MiB run (700 allocations):

| measure | value |
|---|---:|
| free counter saturates at | 58,985,472 B (56.25 MiB), a **nonzero floor** |
| allocations that still succeeded after saturation | **337** |
| genuinely free at saturation, per sysfs | **9.34 GiB** |
| in-process recovery after freeing all 700 | **48.5%** of baseline free |
| recovery after process exit | **full** (sysfs returns to its 2.44 GB baseline) |

The kernel driver is honest throughout: amdgpu sysfs `mem_info_vram_used` tracked the
requested bytes to within rounding at every step. The divergence is entirely SCALE's.

The dangerous shape is not that the counter reads low. It is that **the counter saturates
near zero while allocation keeps working.** Any allocator that asks "can I fit another
layer?" via `cudaMemGetInfo` stops 337 allocations and 3.6 GiB early on this card.

## Why the invariance is the finding

A 4x multiplier means every board loses the same *fraction*. On a 32 GB R9700 the same
defect yields roughly 7.9 GiB reachable; on this 16 GB card, 3.9 GiB. Both are ~24.6%.

That is what makes it a consumer-RDNA4 blocker rather than an annoyance. Atlas serves
`Qwen3.8-27B-NVFP4` at 19.4 GB resident and `Ornith-1.0-9B-NVFP4` at a few GB. Against a
3.9 GiB honest-reporting ceiling, the 27B is unreachable on 16 GB regardless of the defect,
but the 9B sits close enough to the line that anything sizing allocations off
`cudaMemGetInfo` will misjudge it. The sysfs workaround is not an optimization here, it is
load-bearing.

## Two corrections to my own first draft

Both were caught by re-measurement after the first version of this file was written. Kept
visible rather than edited away.

**Correction 1 -- the headline claim was wrong.** The first draft led with "16 GB pays 2.8x
more for this defect than 32 GB," resting on P-S4 and on a ~67% figure inferred from Atlas's
prose. The chunk sweep shows the reachable fraction is board-size **invariant** at ~24.6%,
so there is no disproportionality to claim. The practical conclusion survives (16 GB is
where the absolute ceiling bites) but the mechanism I asserted does not.

**Correction 2 -- the prereg's baseline reasoning was wrong.** The prereg recorded that
SCALE "under-reports usage at baseline by 2.13 GB" and argued this compounds with the
over-charge: "start optimistic, then over-charge from there... worse than either alone."
That framing is wrong. `cudaMemGetInfo` reports **total** as the full 15.92 GiB board and
its free as 15.625 GiB, i.e. it is reporting whole-device capacity while apparently not
accounting for the desktop's 2.6 GB at all. That is plausibly a **separate** defect (the
free counter ignores other processes' allocations), not optimism feeding the 4x. The two
should be reported to Spectral as distinct items.

## Prediction scorecard

| id | prediction | result |
|---|---|---|
| **P-S1** | charge ratio well above 1.0; point estimate 4x, band 3.5-4.5x | **CONFIRMED** -- exactly 4.00x, and now shown invariant across 4/11/32 MiB |
| **P-S2** | **THE FORK.** phantom exhaustion at alloc **#364** (band #300-420), ~9.7 GiB genuinely free | **CONFIRMED** -- onset at **#364**, 9.34 GiB genuinely free |
| **P-S3** | runtime-free does not return to within 98% of baseline | **CONFIRMED but refined** -- 48.5% in-process, full recovery on process exit |
| **P-S4** | 16 GB board **disproportionately** hurt; usable fraction below 30% | **PREMISE FALSIFIED.** The numeric bar passed (24.6% < 30%) but for the wrong reason: the fraction is board-invariant, so 32 GB is hit equally in proportion. Scored as a miss. |

P-S2's point estimate was derived in the prereg as `15.63 GiB x 1024 / 44 MiB = 364` and
landed on 364. That is an arithmetic consequence of the 4x ratio holding exactly, not
independent foresight -- the real content was P-S1's 4x.

P-S4 is the honest failure here. I predicted a disproportionate effect on small boards and
built the first draft's headline on it. The effect is real in absolute terms and absent in
proportional terms, which is a different claim than the one I committed to.

### On Atlas's 32 GB figures

I could not reconcile issue #1119's "22064 [MiB], no recovery" with a clean 4x ratio: at 4x,
an R9700 saturates near 7.9 GiB requested, not 21.5 GiB. The most likely reading is that
they continued allocating well past saturation (as this run did, to #700) and 22064 MiB is
where they stopped rather than where the counter pinned. **This is stated as unreconciled
rather than resolved**, and no comparison figure for the 32 GB board is claimed here.
Confirming it needs their raw trace or a run on R9700 silicon.

## Instrument defect found and fixed

The first version of the probe gated phantom exhaustion on `free < chunk_size`. On gfx1201
the counter saturates at a **nonzero floor of 56.25 MiB** and never reaches zero, so that
test never fired: the first full run printed `phantom exhaustion: NO` on a run that had been
pinned for 337 consecutive allocations. The finding was recovered from the CSV, not from the
probe's own verdict.

Fixed to detect "free counter stopped moving for 8 consecutive successful allocations". The
rebuilt probe fires correctly. It reports the **confirmation** point (#371, after its
8-sample window) while the CSV gives the true onset (#364); the CSV is the record.

Logged because the run would otherwise have been scored as a falsification of P-S2 by an
instrument bug rather than by the hardware.

## Second finding: SCALE 1.7.3 does not compile on current glibc

Unrelated to memory, hit while building the probe, and a blocker for anyone on a modern distro.

SCALE force-includes `redscale_impl/builtins.h`, which declares `__host__ __device__ double
rsqrt(double)` among others. glibc 2.44 exposes `rsqrt`, `cospi`, `rootn` and `powr` as C23
math functions, gated on `__GLIBC_USE (IEC_60559_FUNCS_EXT_C23)`, which is enabled by
`__USE_GNU` -- and clang defines `_GNU_SOURCE` automatically for C++ on Linux. Result:

```
error: __host__ function 'rsqrt' cannot overload __host__ __device__ function 'rsqrt'
```

Confirmed it is glibc and not the compiler: `-ccbin g++-15` does not help, because the
declarations live in `/usr/include/bits/mathcalls.h`, shared across GCC versions.

**Workaround**: `-U_GNU_SOURCE`. That in turn breaks libstdc++ headers needing `_GNU_SOURCE`
for wide-char support (`<cwchar>`, pulled in by `<vector>` and `<string>`), so the probe is
written against C headers only. Fine for a standalone repro, not a general answer -- real
code cannot simply give up `<vector>`.

SCALE's supported distros are Ubuntu 22.04/24.04 and Rocky/RHEL 8/9, all shipping older
glibc, so this is invisible on the tested platforms and will bite every Arch, Fedora
Rawhide, and newer-Ubuntu user.

## Environment

| item | value |
|---|---|
| GPU | AMD Radeon RX 9070 XT, gfx1201, RDNA 4, 15.92 GiB |
| SCALE | 1.7.3 tarball, sha256 `869afb15e6a947c7966cdf9408633eab6390b21ddae3755538eba3127c6871da`, fetched 2026-09-17T16:00:48Z |
| ROCm | 7.2.4 |
| OS | CachyOS, kernel 7.2.3-1-cachyos (SCALE does not list Arch as supported) |
| glibc / gcc | 2.44 / 16.2.1 |
| desktop resident on card | yes, ~2.6 GB, same as the Atlas reference setup |
| build | `nvcc -U_GNU_SOURCE -o meminfo_probe meminfo_probe.cu` |
| run | `LD_LIBRARY_PATH=$SCALE/targets/gfx1201/lib ./meminfo_probe <chunk_mib> <max_allocs> <csv>` |

**On `-U_GNU_SOURCE` as a confound:** it was required to compile at all (see above) and it
changes only libc *header* feature exposure at compile time. The measured path is
`cudaMalloc` / `cudaMemGetInfo` inside SCALE's runtime plus `fopen`/`fscanf` on sysfs, none
of which have `_GNU_SOURCE`-dependent variants. The 4.00x ratio also reproduces identically
across three separately compiled runs. It cannot account for the result.

Also noted from `scaleinfo`, for the upstream report: constant memory is reported as
2147483647 B, which is `INT_MAX` and not a real quantity; LDS is reported as 65536 B, the
64 KB cap carried over from gfx1151. The latter is relevant to atlas #1116, which wants the
W4A16 prefill GEMM retiled for RDNA 4 -- an LDS ceiling below the hardware's constrains
exactly that retiling.

## Filed upstream 2026-09-17

- **Spectral Compute:** https://github.com/spectral-compute/scale-validation/issues/67
  (the 4.00x over-charge), https://github.com/spectral-compute/scale-validation/issues/69
  (the glibc 2.41+ compile failure). Both carry `scale_bugreport_sanitized.txt` -- the raw bundle
  was scrubbed of the hostname and the root filesystem UUID before publication.
- **Atlas #1119:** commented with the 1.7.3 reproduction, the chunk-size sweep, the
  in-process-vs-exit recovery refinement, and the unreconciled 22064 question.
- **Discord:** pointer posted in the SCALE channel linking all three tickets.
- Drafts as submitted are in `drafts/`.

## Not tested here

The `cuModuleGetFunction` defect (returns `CUDA_SUCCESS` with an unusable handle for an
undefined symbol) is a separate probe and was out of scope by prereg.
