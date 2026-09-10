# Third-party data: the Qwen calibration trend across three generations

**Date:** 2026-09-07 · **Source:** Artificial Analysis, AA-Omniscience, read from screenshots
supplied by the operator, **captured earlier the same day and already superseded — see the
volatility warning at the end of this file.** **Third-party data — not our measurement.** Recorded because it is
the within-lineage comparison our own corpus lacks, and because our matched effort ladder
bears on how one of its numbers should be read.

## The figures as shown

| model | accuracy | non-hallucination (1 − hallucination) |
|---|---:|---:|
| Gemini 3.1 Pro Preview | **55 %** | 49 % |
| Qwen3.5-27B | 21 % | **19 %** |
| Qwen3.6-27B | 20 % | 51 % |
| Qwen3.6-35B-A3B | 19 % | 49 % |
| Qwen3.8-27B (xhigh) | 16 % | **70 %** |

## Two readings this supports

**1. A deliberate, monotone trade across generations at a fixed size class.**
27B class: non-hallucination **19 → 51 → 70**; accuracy **21 → 20 → 16**. Calibration nearly
quadrupled while knowledge drifted down. Three generations moving one way on both axes is
hard to read as incidental.

**2. Active parameters barely move either metric, within a generation.**
Qwen3.6-27B (dense) vs Qwen3.6-35B-A3B (3B active): accuracy 20 % vs 19 %, non-hallucination
51 % vs 49 %. **Nine times fewer active parameters, ~1 point on each axis.** These are
undamaged models, so this is cleaner than anything derivable from our REAP arms — and it cuts
against the prior intuition that low active-parameter count should itself degrade calibration.

Note this does **not** rehabilitate `RESULT_QWEN_CALIBRATION_CONTRAST.md` as a control (see
`FAILURE_MODES.md` AFM-30). That arm was REAP-*damaged*; these are stock models.

## What our own measurement adds

**AA's 70 % for Qwen3.8-27B is measured at `xhigh`, which our matched ladder found is the
model's *worst* calibration setting.** From `RESULT_A6_LOW_RUNG.md`, same weights, same
fixture, same card sampling, 24 trials per arm:

| | xhigh | medium | low |
|---|---:|---:|---:|
| unanswerable ABSTAINED | 13/24 | 21/24 | 21/24 |
| confabulated | 6/24 | 3/24 | 3/24 |
| NO-STOP | 5/24 | 0/24 | 0/24 |

Confabulation halves at `medium`. If that carries to AA's instrument, Qwen3.8's published
70 % understates what the model does at a better setting — and no published hallucination
figure we have seen reports the effort level it was measured at.

`RESULT_EFFORT_IS_A_PROMPT_EDIT.md` is why this is not a nitpick: `reasoning_effort` is a
**207-character injected system string**, not a compute knob, and `medium` injects nothing at
all. The reported number is a property of a prompt the benchmark chose.

## What cannot be checked from screenshots

- **Measured vs estimated.** The AA Intelligence Index crop hatches `medium` and `low` as
  *"Estimate (independent evaluation forthcoming)"*, with only `xhigh` solid. Whether the
  3.5-27B and 3.6-27B bars here are measured is **not determinable** from the image. If any
  are estimates, the generational trend is partly projection.
- **Architecture continuity.** Qwen3.8-27B is confirmed dense/hybrid from its own GGUF
  metadata. What 3.5-27B and 3.6-27B are is unknown to us. "27B" is a size label, not an
  architecture, and a lineage claim needs the architectures to line up.
- **Harness and sampling.** Unknown for all rows. How a non-terminating response is scored is
  not a small detail here — we measured 5/24 NO-STOP at `xhigh` on this exact model.

## Status

**Not a result of ours.** Suitable as context and as motivation for a matched experiment;
not citable as our measurement. The claim we can make from our own data is narrower and
solid: on one fixture, `reasoning_effort` moves this model's confabulation rate by 2× at
fixed weights, and published hallucination figures do not report it.


## VOLATILITY WARNING — added 2026-09-07, hours after the figures above

**The figures in this note are not stable and cannot be re-verified against the live site.**
Within the same afternoon, screenshots showed:

| | earlier capture | later capture |
|---|---|---|
| Intelligence Index version | (unlabelled) | **v4.3**, "10 evaluations" |
| Terminal-Bench | **v2.1** | **v4.0** |
| model pool | 519 | **644** |
| Qwen3.8-27B (xhigh) index score | **41** | **34** |
| Qwen3.8-27B medium / low index | 35 / 34, hatched as *estimates* | not shown |
| AA-Omniscience hallucination chart | 31 models, incl. Qwen3.8-27B plain 18 %, low 53 %, medium 67 % | 28 models, those three absent |

The 41 → 34 move is **not a model change**. The index changed composition. Both numbers are
correct, for different indices, published under the same name.

Whether the three Qwen3.8-27B effort entries were withdrawn by the publisher or merely absent
from the operator's filter state is **not determinable** from the screenshots — they had been
added manually to the earlier view.

**Consequence for anything built on this note:** every AA figure quoted above is
version-and-time-specific and none of it can be cited as a stable reference. That includes the
generational lineage table, which is the part most likely to be quoted. Treat the whole file as
a snapshot with an unknown expiry, not as a source.

**The measurement it motivated is unaffected.** `RESULT_SEARCH_ASYMMETRY.md` and
`RESULT_A6_LOW_RUNG.md` are our own, on pinned builds, pinned clocks, pinned sampling and a
versioned fixture. That is the whole argument for the pinning discipline: a third-party
leaderboard that does not version its own history cannot be used as a time series, and any
claim resting on one inherits its volatility.
