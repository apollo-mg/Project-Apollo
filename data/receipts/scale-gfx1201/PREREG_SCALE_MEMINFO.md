# Prereg -- does SCALE's cudaMemGetInfo tell the truth on consumer gfx1201?

**Written 2026-09-17, before the probe was run.** Predictions are committed here first; the
result file scores them mechanically and keeps the wrong ones.

## Why this test

Avarok/atlas issue #1119 reports two SCALE 1.7.1 defects on gfx1201, both already worked
around in PR #1107:

- `cudaMemGetInfo` over-charges per allocation. Their measurement: about 44 MiB charged per
  11 MiB requested (4x). After ~2000 iterations SCALE reported zero free while sysfs showed
  ~21 GB genuinely free, and it did not recover after the allocations were released.
- `cuModuleGetFunction` returns `CUDA_SUCCESS` with an unusable handle for an undefined
  symbol, deferring the error to launch time.

Atlas measured these on an **R9700, 32 GB, SCALE 1.7.1**. Two things differ here and either
one could change the answer:

1. **Hardware**: RX 9070 XT, **16 GB consumer** board, same gfx1201 ISA, with a desktop
   session resident on the card. If the over-charge is real, a memory-accounting defect is
   far more dangerous at 16 GB than at 32 GB: there is less headroom to absorb it.
2. **Version**: the current tarball is **SCALE 1.7.3**, not the 1.7.1 Atlas tested. The
   defect may already be fixed upstream, which would mean Atlas can retire both workarounds.

This probe needs only SCALE and a GPU. No Atlas build, no model weights.

## Environment (recorded before the run)

| item | value |
|---|---|
| GPU | AMD Radeon RX 9070 XT, gfx1201, RDNA 4 |
| VRAM total | 17,095,983,104 B (15.92 GiB) |
| SCALE | 1.7.3 (tarball, sha256 `869afb15e6a947c7966cdf9408633eab6390b21ddae3755538eba3127c6871da`) |
| ROCm | 7.2.4 |
| OS / kernel | CachyOS, 7.2.3-1-cachyos (SCALE does not officially support Arch) |
| Atlas reference stack | R9700 32 GB, SCALE 1.7.1, ROCm 7.2.0, Ubuntu 24.04, kernel 7.0 |
| desktop resident on card | yes, both here and in the Atlas reference |

## Already OBSERVED, not predicted

Recorded before writing the probe, so it is not scored below:

- **At rest, with no allocations, SCALE and the kernel driver disagree by 2.13 GB.**
  `scaleinfo` reports 16,779,574,272 B free of 17,095,983,104 B total, implying 0.32 GB used.
  amdgpu sysfs `mem_info_vram_used` reports 2,451,259,392 B (2.45 GB) used by the desktop.
  SCALE is **under**-reporting usage at baseline, the opposite direction from the Atlas
  over-charge. Both can hold at once: start optimistic, then over-charge from there. That
  combination is worse than either alone, because the optimism is spent before you begin.
- `scaleinfo` reports constant memory as 2147483647 B, which is `INT_MAX` and not a real
  quantity. Cosmetic, noted for the upstream report.
- `scaleinfo` reports shared memory (LDS) as 65536 B. This is the 64 KB cap carried over
  from gfx1151. Relevant beyond this probe: atlas #1116 wants the W4A16 prefill GEMM
  retiled for RDNA 4, and an LDS ceiling below what the hardware offers constrains exactly
  that retiling.

## Predictions

Arithmetic behind the numbers: real headroom at start is 15.92 - 2.28 = **13.64 GiB**, so at
a truthful 1.0x charge ratio an 11 MiB chunk loop reaches real exhaustion near **1267**
allocations. At the Atlas-measured 4x, SCALE's own optimistic 15.63 GiB baseline is consumed
after 15.63 * 1024 / 44 = **364** allocations.

| id | prediction | falsified if |
|---|---|---|
| **P-S1** | Charge ratio is materially above 1.0. Point estimate **4x** (Atlas), band 3.5x-4.5x | ratio stays within 1.0-1.2x through the run |
| **P-S2** | **THE FORK.** Phantom exhaustion occurs: runtime-free drops below one chunk while sysfs still shows real headroom. Point estimate alloc **#364**, band #300-#420, with about **9.7 GiB** genuinely free at that moment | no phantom exhaustion before alloc #1200, i.e. the loop runs to real exhaustion |
| **P-S3** | After releasing every allocation, runtime-free does **not** return to within 98% of baseline (Atlas: "no recovery") | runtime-free returns to >=98% of baseline |
| **P-S4** | The 16 GB board is hurt disproportionately: usable fraction before phantom exhaustion is **below 30%** of real VRAM (Atlas on 32 GB got ~22 GB of 32 GB, ~69%) | usable fraction is >=50% |

## Amendment 1 -- safety cap on the allocation loop (2026-09-17, before the run)

The probe runs on the card driving the desktop session. If P-S2 is falsified (no phantom
exhaustion), the loop would continue to *real* exhaustion at roughly alloc #1267, starving
the compositor and plausibly freezing the session. So `max_allocs` is capped at **700**
(7.52 GiB requested worst case, leaving about 6.1 GiB for the desktop).

This changes P-S2's falsification criterion, stated here before any data is seen: the
original text said "no phantom exhaustion before alloc #1200", which the cap makes
unreachable. **Revised: P-S2 is falsified if the loop reaches alloc #700 with no phantom
exhaustion.** That is 1.67x beyond the upper edge of the predicted #300-420 band, so it
remains a real test rather than a weakened one. P-S1, P-S3 and P-S4 are unchanged.

If the run reaches #700 cleanly, the remaining question (does it eventually hit real
exhaustion gracefully?) is worth answering, but on a card with no desktop on it, not this one.

## What each outcome means

- **P-S1/P-S2 confirmed**: the defect survives into 1.7.3 and is worse on 16 GB. Atlas keeps
  its workarounds, the upstream report to Spectral gains a severity axis it did not have
  (capacity-dependent, not cosmetic), and consumer RDNA 4 needs the sysfs path as a hard
  requirement rather than a fallback.
- **P-S1/P-S2 falsified**: 1.7.3 fixed it. That is directly actionable for atlas #1119,
  whose acceptance criteria call for retiring the workarounds behind feature flags once a
  SCALE fix is verified. A clean falsification here is worth more to them than a confirmation.

Either way the probe and its CSV satisfy #1119's first acceptance criterion: a standalone
repro under `scripts/scale-probe/` with SPDX headers and recorded output.

## Deliberately out of scope

The `cuModuleGetFunction` defect is a separate probe and is not tested here.
