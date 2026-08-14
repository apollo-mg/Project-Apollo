# Qwen 3.8 27B `UD-IQ2_M`: 8/8 with thinking, 8/8 without. The gap is zero.

**Date:** 2026-08-14, launch day. Predictions sealed in `PREREG.md` before any run.
**Hardware:** RX 9070 XT 16 GB, model fully resident (`-ngl 999`), f16 KV, `-fa on`,
**no** TurboQuant KV, **no** MTP draft, `-c 8192`. Quant is the only variable.
**Sampling:** `temperature 0`, `top_k 1`, `seed 1234`, `n_predict 512`.

## Result

8 prompts x {thinking on, thinking off}. Every gradeable item correct in **both** arms.

| prompt | ground truth | think=on | think=off |
|---|---|---|---|
| factual | Canberra | OK (34 tok) | OK (3 tok) |
| arith | 252 | OK (92) | OK (172) |
| reason | 2:29 | OK (126) | OK (414) |
| loopbait | all 8 planets, then stop | OK (89) | OK (48) |
| format | exactly 3 colors, one per line | OK (244) | OK (6) |
| code | working `is_palindrome` | OK (295) | OK (39) |
| refuse | 1/0 undefined | OK (67) | OK (2) |
| longform | <= 4 sentences | OK (261) | OK (96) |

**Stop-reason census — the thing this harness exists to record:**

| arm | finish reasons | loops | mean tokens |
|---|---|---|---|
| thinking=on | `{stop: 8}` | 0 | 151 |
| thinking=off | `{stop: 8}` | 0 | 97 |

Zero cap-deaths, zero repetition loops, zero truncations, in either arm.

## Scoring the sealed predictions

| # | prediction | conf | outcome |
|---|---|---|---|
| P1 | thinking gap larger at IQ2 than IQ3 | 0.70 | **cannot resolve** — the IQ2 gap is 0 pp, so there is no gap to be larger. Awaiting IQ3 |
| P2 | IQ2 gap smaller than Puzzle's 25.0 pp | 0.60 | **CONFIRMED**, and by more than intended: 0 pp vs 25.0 pp |
| P3 | thinking-off produces >= 1 loop or non-stop failure in 20 prompts | 0.55 | **FALSIFIED** — 0 of 8, all `stop` |
| P4 | failures, if any, are stopping-rule not wrong-answer | 0.65 | **vacuous** — no failures of either kind |
| P5 | IQ3 thinking-on within 5 pp of IQ2 thinking-on | 0.50 | pending |

## What this does and does not say

**It does not replicate the Puzzle substitution finding.** On
Nemotron-Puzzle-75B-A9B the thinking gap was 25.0 pp at Q2 and 3.3 pp at IQ4.
Here it is **0 pp at IQ2**, on a quant carrying **96 `IQ1_M` tensors** — a full tier below
its own label, and the most aggressive file in the ladder.

The honest reading is not "the Puzzle finding is wrong." It is that **this test lacks the
resolution to measure it.** Eight hand-checkable prompts on a strong 27B is a ceiling test:
both arms score 100%, so no gap of any size could appear. The Puzzle result used
HumanEval+, 164 problems, K=3 — 492 samples per cell against 8 here.

What survives as a real observation is narrower and still useful: **`UD-IQ2_M` is not
brittle.** Going in, the expectation from this fleet's own history was schema loops,
cap-deaths, and "2-Bit Drunk" degradation at 2-bit. On a dense 27B with 96 `IQ1_M` tensors,
none of it appeared — clean stops, correct arithmetic, correct multi-step time reasoning,
correct instruction-following down to "exactly three, one per line", and code that runs.

**The token-count asymmetry is the one suggestive signal.** Thinking-off used *more* tokens
on the two multi-step items (arith 172 vs 92, reason 414 vs 126) because it reasons in the
visible channel instead of a think block, then still lands on the right answer. Whatever
the model needs to solve these, it does either way; the channel changes, not the outcome.

## Limits

- **K=1.** `agent-benchmark-determinism` records temp-0 on this fleet as non-reproducible
  (HA-04 bistable 35/100/100/35). This is an existence proof, not a rate.
- **8 prompts, hand-graded, ceiling effect.** Discriminating power near zero at this
  difficulty. A real replication needs HumanEval+ or equivalent at K>=3.
- **One ordering.** Thinking-on ran first in both arms; not reversed.
- Nothing here measures quality *differences* between correct answers — only correctness.

## Next

`UD-IQ3_XXS` for the same 2x2, which at minimum tests P5 and tells us whether the 96
`IQ1_M` tensors in `UD-IQ2_M` cost anything measurable. If IQ3 also scores 8/8 — likely —
then the prompt set is the limiting instrument and the honest move is to escalate to a
harder benchmark rather than report a null as a finding.
