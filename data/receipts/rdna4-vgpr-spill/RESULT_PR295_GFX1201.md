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
