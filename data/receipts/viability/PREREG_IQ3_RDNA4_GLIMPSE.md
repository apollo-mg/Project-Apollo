# PREREG — does abstention survive to IQ3? (RDNA4 glimpse, deliberately confounded)

**Written 2026-09-07 before the run.** Scored honestly, misses included.

## What this is and is not

A **glimpse**, not the quant-calibration study. `.194` is committed to the clause arms, so
this runs on the desktop 9070 XT instead — which changes **quant, hardware, backend and
build** all at once against the Q6_K ladder it will be compared with:

| | Q6_K ladder (2026-08-21 / 09-07) | this run |
|---|---|---|
| model | `Qwen3.8-27B-Q6_K` 21.30 GiB | `Qwen3.8-27B-AD-IQ3_XXS` 11.25 GiB |
| node | `.194`, 4× P100 sm_60 | desktop, RX 9070 XT gfx1201 |
| backend | CUDA | HIP/ROCm |
| binary | `llama_stock/build_puzzle` `73a55486c` | `engines/tq_head/build_rocm` |
| packager | stock Qwen | AD (imatrix recipe differs) |

`AFM-20` names exactly this failure — a ladder that varies one thing over a fixed
everything-else is n=1 on everything else. **Here it is worse: four things move together.**
So a difference between this and Q6_K is attributable to *none* of them individually. The run
is worth doing only because of its asymmetry:

- **If abstention HOLDS at IQ3** (≈21/24, 24/24 answerable): informative. Four adverse
  changes at once failed to break it, which is evidence of robustness under the strongest
  version of the confound. Supports the operator's 16GB thesis provisionally.
- **If abstention DEGRADES**: uninformative on cause. Could be quant, packager, backend or
  build. Motivates the controlled study on one box; proves nothing on its own.

Recorded up front so a degradation cannot later be reported as "IQ3 breaks calibration".

## Conditions

`--tier cal --effort xhigh` and `--effort medium`, `--sampling card`, seeds 1001–1003,
`-c 8192` to match the escalation ceiling of the reference arms. Both effort levels because
the reference ladder's headline is the **gap between them** (13/24 vs 21/24) — a gap is more
robust to the confounds above than either absolute number.

## Predictions

| # | prediction | conf |
|---|---|---:|
| R1 | `medium` abstention ≥ 19/24 — abstention substantially survives IQ3 | 0.65 |
| R2 | The medium-vs-xhigh **gap persists**: medium abstains ≥ 5 more than xhigh | 0.70 |
| R3 | Answerable arm drops below 24/24 — IQ3 costs knowledge the Q6_K had | 0.55 |
| R4 | `CAL-U3` answers `1906` on ≥ 5 of 6 runs — the false-premise-with-real-entities failure is quant-invariant | 0.70 |
| R5 | `CAL-U5` does **not** reproduce its greedy `.194` runaway here, consistent with the 08-21 observation on this same file | 0.60 |

R3 is the one that would most complicate the operator's pitch: if IQ3 keeps its calibration
but loses answerable accuracy, "it won't feed you bullshit" holds while "it works really well"
weakens. Those are separable and the fixture measures both.

R4 matters for the cue-vs-uncertainty question. If abstention is a **trained cue-triggered
habit**, it should be cheap to represent and survive quantisation; an item with no cue
(`CAL-U3`, all entities real) should keep failing at every bitrate. If abstention is
**emergent epistemic**, low-bit noise should perturb it and U3's failure should become less
deterministic.

## Stopping rule

3 reps × 2 efforts, then score. Same peek rule as `PREREG_CLAUSE_DECOMP.md` Amendment 1:
an interim look may only trigger an abort, never an extension.
