# PR #295 on RDNA4: 57 of 98 spilling FA kernels fixed, none regressed — but 128 and 256 are not cleared

**PR:** `TheTom/llama-cpp-turboquant#295` — *"fattn-vec: split the turbo K dot at D>128 to stop
the VGPR spill (#294) — needs AMD validation"*, revision `f050a2501`
(*"gate the turbo K split on the LUT, not on D"*).
**Date:** 2026-08-16 · **Target:** `gfx1201` (RX 9070 XT, RDNA4) · **ROCm:** 7.2.4
**Method:** build-only, `-DGGML_HIP=ON -DGPU_TARGETS=gfx1201 -DGGML_HIP_EXPORT_METRICS=On`
— identical to the 2026-08-14 baseline run so the comparison is matched. No benchmark, no
runtime, no quality gate. Raw logs: `gfx1201_pr295_metrics.log.gz` (after),
`gfx1201_build_metrics.log.gz` (before). Parser: `parse_spills.py`.

**Parser validated against the published baseline** — it reproduces that run's headline
figures exactly (98 FA kernels spilling, worst 735), so the delta below is like-for-like.

## Result

| | baseline `fca3093c9` | **PR295 `f050a2501`** | delta |
|---|---:|---:|---:|
| `flash_attn_ext_vec` kernels | 348 | 348 | — |
| **FA kernels spilling** | **98** | **41** | **−57** |
| **worst FA VGPR spill** | **735** | **357** | **−378** |
| all kernels spilling | 209 | 153 | −56 |
| worst spill, any kernel | 865 | 865 | unchanged (non-FA) |

**By head size — the question the PR asks:**

| head size | before | after |
|---|---:|---:|
| 256 | 55 | **33** |
| 128 | 40 | **8** |
| 64 | 3 | **0** |

**57 kernels fixed. Zero newly spilling.** Pure improvement, no regressions introduced at the
resource-usage level.

## Answering the PR's open question directly

> *"whether the fix eliminates spills at both 128 and 256"*

**It substantially reduces both and eliminates neither.** hsk=64 is fully cleared. hsk=128 drops
80 % (40 → 8). hsk=256 drops 40 % (55 → 33) and remains the largest remaining group. The worst
single spill halves, 735 → 357, so the surviving spillers are also less severe — none are
pinned at the 256-VGPR architectural cap the way the baseline's worst ten were.

The revised LUT gate is clearly the right direction: the first version reportedly missed
hsk=128 entirely, and this one clears 80 % of them.

## What this does NOT answer

- **The performance question.** The PR's second open point — whether it avoids the 12–31 %
  turbo2 decode regression on `ncols=1` turbo2/turbo3 — needs a runtime benchmark. This is
  build-only. Worth running now that the spill numbers justify it.
- **Correctness.** No quality gate, no capture run. Fewer spilled registers is not evidence of
  correct output.
- **Other targets.** gfx1201 only. The issue's original gfx908 numbers are not re-measured here.
- **The 41 survivors.** Not investigated — whether they share a template shape, or whether the
  LUT gate simply cannot reach them, is open.

---

## Post-merge analysis: the 41 survivors, mapped onto TheTom's residual buckets

Added after #295 was merged. TheTom's merge comment lists three known residuals and asks
whether the third is "common rather than a single instance". gfx1201 answers that, and
qualifies one of the merge's headline claims.

### Against his three buckets

| bucket | on gfx1201 | max VGPR | note |
|---|---:|---:|---|
| **#2** K=Q4_0 @ D=256, non-turbo `nthreads_KQ_q`, pre-existing | **4** | **357** | **confirmed**, and byte-unchanged before→after (357→357, 336→336, 226→226, 206→206) exactly as "pre-existing" predicts. His arches: 428/341/385. |
| **#1** D=256 ncols>=2 turbo-K, V-side accumulator | **18** | 57 | **confirmed present**, but NOT "identical under both gates" here — these fell **698 → 57**, **681 → 57**, **661 → 36**. On his arches they were already <=22/62/23 before the fix; on RDNA4 they were 625–735 and the gate cut them by ~90 %. |
| **#3** D=128 ncols=1 turbo-K, inside the LUT path | **0** | — | **does not occur on gfx1201.** Evidence that the gfx1100 instance is architecture-specific rather than a common pattern — i.e. against needing the larger "teach the LUT paths to stride and reduce" change. |

### A qualification to the merge justification

> *"All 15 `<128,2,turbo-K,*>` shapes went from 173-421 VGPR spill to zero"*

**On gfx1201 that class does not reach zero.** It improves 80–95 % and survives:

| shape | before | after |
|---|---:|---:|
| `<128,2,TURBO3,TURBO3>` | 243 / 244 | **57 / 54** |
| `<128,2,TURBO2,TURBO3>` | 271 / 272 | **37 / 36** |
| `<128,2,TURBO4,TURBO3>` | 246 | **37 / 36** |
| `<128,2,TURBO3,Q8_0>` | 424 / 424 | **23 / 23** |

RDNA4 was not in the three-architecture sweep (gfx1030 = RDNA2, gfx1100/gfx1103 = RDNA3), and
it differs from all three on precisely the shape class cited as fully cleared.

### A fourth bucket not in his list

19 survivors are **`Q8_0`-K pairs at D=256, ncols=2** — `Q8_0`/TURBO2 (61, 60), `Q8_0`/F16
(40, 40), `Q8_0`/BF16 (32), `Q8_0`/TURBO4 (28, 25) — plus `BF16`/`BF16` (13) and `F16`/`F16`
(1). **All byte-unchanged before→after.** Same structural story as his Q4_0 residual: a
non-turbo K path the gate does not touch, just at a different type. Low magnitude, but it is
the same mechanism and belongs on the list.

### Scale context

gfx1201 starts far worse than any arch in the sweep and ends far worse:

| arch | spilling before→after | worst before→after |
|---|---|---|
| gfx1030 (RDNA2) | 40 → 3 | 294 → 23 |
| gfx1100 (RDNA3) | 42 → 10 | 421 → 37 |
| gfx1103 (RDNA3) | 40 → 2 | 298 → 25 |
| **gfx1201 (RDNA4)** | **98 → 41** | **735 → 357** |

The fix is a larger absolute win on RDNA4 than anywhere else (−57 kernels, −378 worst), and
RDNA4 still carries 4–20x the residual count of the other three.
