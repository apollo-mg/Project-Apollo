# RDNA4 spills too — and worse, and not only at head size 256

**Issue:** `TheTom/llama-cpp-turboquant#294` — *"HIP: turbo K-cache flash-attention spills
295-720 VGPRs at head size 256 on CDNA/RDNA2/RDNA3 (quality gate had never run)"*
**Date:** 2026-08-14 · **Commit:** `fca3093c9` (`feature/turboquant-kv-cache`, the default
branch) · **Target:** `gfx1201` (RX 9070 XT, RDNA4) · **ROCm:** 7.2.53211-3d9ef42
**Method:** build-only. `-DGGML_HIP_EXPORT_METRICS=On`, which is
`-Rpass-analysis=kernel-resource-usage` — a compile-time remark pass. No benchmark, no
capture run, no quality gate. Raw log archived as `gfx1201_build_metrics.log.gz`.

## Why this run exists

The issue's title says CDNA/RDNA2/RDNA3, but every number in its body comes from **one
target**: `-DGPU_TARGETS=gfx908`. RDNA3 in the title is from jasstrong's separate #252/#253
reports on gfx1100; RDNA2 has no supporting data in the body at all. **RDNA4 is absent
because nobody compiled for it**, not because it is clean — the author states plainly:
*"I have no AMD hardware, so I can take this no further than the CI metrics."*

7034 kernels analysed, 346 of them `flash_attn_ext_vec`.

## Result: confirmed on RDNA4, and larger

| | gfx908 (issue #294) | **gfx1201 (this run)** |
|---|---|---|
| worst FA spill | 330 | **735** |
| spill range on FA | 295-330 | 1-735 |
| head sizes affected | 256 only | **256, 128, and 64** |
| FA kernels spilling | not stated | **98 of 346** |

**Worst ten, all at hsk=256, all pinned at the 256-VGPR architectural cap with occupancy 5
waves/SIMD:**

| hsk | K | V | mask | VGPR | spill | scratch B/lane |
|---|---|---|---|---|---|---|
| 256 | TURBO2_0 | F16 | 0 | 256 | **735** | 2608 |
| 256 | TURBO2_0 | F16 | 1 | 256 | 708 | 2496 |
| 256 | TURBO4_0 | Q8_0 | 0 | 256 | 704 | 2556 |
| 256 | TURBO2_0 | TURBO2_0 | 0 | 256 | 698 | 2624 |
| 256 | TURBO3_0 | TURBO2_0 | 1 | 256 | 696 | 2688 |
| 256 | TURBO2_0 | Q8_0 | 0 | 256 | 690 | 2500 |
| 256 | TURBO3_0 | F16 | 1 | 256 | 687 | 2592 |
| 256 | TURBO2_0 | TURBO3_0 | 0 | 256 | 682 | 2752 |
| 256 | TURBO2_0 | TURBO2_0 | 1 | 256 | 681 | 2576 |
| 256 | TURBO3_0 | TURBO3_0 | 1 | 256 | 680 | 2752 |

## Three ways this differs from the gfx908 picture

**1. It is not confined to head size 256.** The issue states *"Every flagged
flash-attention instantiation is at head size 256."* On gfx1201, spilling FA kernels break
down as **256: 55, 128: 40, 64: 3**. Forty spilling kernels at hsk=128 is the shape the
suite *does* currently test, and it is the shape ordinary models use.

**2. It is not only TURBO4_0 as K.** The issue states *"every one has TURBO4_0 as the K
type."* K-type distribution among the 98 spillers here:

`TURBO4_0: 41, TURBO3_0: 21, TURBO2_0: 21, Q8_0: 7, Q4_0: 4, F16: 2`

TURBO4_0 leads, but all three turbo K types spill, and the single worst kernel has
**TURBO2_0** as K. Of the 98, **83 involve a turbo K type; 11 involve no turbo type at
all** — so a residue exists that is not attributable to this fork's types and is worth
diffing against a clean upstream build, exactly as the issue suggests for the Q2_K
`mul_mat_q` case.

**3. Magnitude is roughly 2.2x the CDNA worst** (735 vs 330). All ten worst are capped at
256 architectural VGPRs with occupancy 5 — the allocator has run out of registers and is
pushing 2.5-2.75 KB per lane to scratch.

## Correction recorded

An earlier pass of this analysis mislabelled every turbo type. The enum was read from the
stale `engines/llama_cpp_turboquant` checkout (`c26cbdffc`), where
`TURBO2_0=42, TURBO3_0=43, TURBO4_0=44`. The worktree actually built (`fca3093c9`) has
`TURBO2_0=43, TURBO3_0=44, TQ3_1S=45, TQ4_1S=46, TURBO4_0=47, COUNT=48`.

**The issue's mapping is correct and this analysis was briefly wrong.** Every type label in
the tables above uses the built tree's enum. Anyone reproducing this must read `ggml.h`
from the same commit they compiled, because the turbo type IDs move between commits.

## Limits

- **Compile-time only.** Spilling is not a correctness bug; this says nothing about
  #252/#253 V-cache corruption on gfx1100, and no claim is made that the two are related.
- **No performance measurement.** Occupancy 5 and 2.5 KB/lane of scratch traffic predict a
  cost; that prediction is untested here.
- **Does not reproduce the issue's exact CI condition.** #293's `nodiscard` fix is not on
  the default branch yet, so this is the current branch at gfx1201, not gfx908's build
  conditions transplanted. gfx1201 numbers are new either way.
- **One target, one ROCm version.** No claim about RDNA2 or RDNA3, both of which remain
  uncompiled in this project.
