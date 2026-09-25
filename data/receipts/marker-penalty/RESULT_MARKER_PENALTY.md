# A logit penalty on 20 hesitation-marker tokens costs no calibration, but shortens Qwen3.8-27B's thinking only modestly: significant at IQ3_XXS (0.77x), not at Q6_K (0.86x, p = 0.32)

**2026-09-25 10:43-14:36, `.194`**, split into two 2-GPU testers (Q6_K on GPUs 0,1; UD-IQ3_XXS on 2,3), buun
`08826ad6e`, `-c 16384 -np 1 -fa on --kv-unified -ctk f16 -ctv f16 -sm tensor`. The CAL instrument
(`viability/run_fixture_structfix.py --tier cal --sampling card --effort xhigh`, `n_predict` 6144): 16 items, 3 reps
(seeds 1001-1003), rotated arm order. **288 generations, 0 failures.** Prereg: `PREREG_MARKER_PENALTY.md` (committed
`befc0e5` before any generation). Scorer: `analyze_marker.py` -> `RESULT_marker.json`. Raw: `raw/`.

**Arms:**
- `A`: no penalty.
- `B`: `logit_bias` -2 on the 20 marker tokens (`marker_ids.json`).
- `C`: `logit_bias` -4 on the same tokens.

The markers are the single-token forms of Wait, But, Hmm, Actually, Alternatively, However, Hold, Oh, Maybe and
Perhaps: the class scored in `quant-hesitation/`.

## Per arm

| model | arm | answerable correct | unanswerable: abstained / wrong / fail* | NO-STOP | median thinking chars (unanswerable) | total thinking chars | completion tokens | penalized markers / 1k chars |
|---|---|---:|---|---:|---:|---:|---:|---:|
| Q6_K | A | 24/24 | 20 / 3 / 4 | 1 | 3,438 | 183,024 | 52,625 | 2.38 |
| Q6_K | B | 24/24 | 18 / 5 / 6 | 1 | 2,148 | 149,580 | 47,475 | 0.46 |
| Q6_K | C | 24/24 | 20 / 4 / 4 | 0 | 1,573 | 152,788 | 41,990 | 0.14 |
| IQ3_XXS | A | 23/24 | 23 / 1 / 1 | 0 | 4,132 | 260,449 | 71,520 | 2.42 |
| IQ3_XXS | B | 24/24 | 22 / 2 / 2 | 0 | 3,116 | 171,218 | 48,228 | 0.62 |
| IQ3_XXS | C | 24/24 | 22 / 2 / 2 | 0 | 2,888 | 156,512 | 43,270 | 0.10 |

*fail = ANSWERED-WRONG + NO-STOP on the unanswerable half (of 24).

## Scored against the prereg

Per-item statistic: log(mean thinking chars in the arm / in A), averaged over the 16 items. Exact sign-flip
permutation over items.

| # | claim | result | verdict |
|---|---|---|---|
| M1 | C shortens thinking at Q6_K: ratio < 0.85, p < 0.05 | **0.858**, p = 0.32, 8/16 items shorter (B: 0.841, p = 0.16) | **FAIL** |
| M2 | no calibration cost (answerable >= A - 2, unanswerable fail <= A + 2) | Q6_K: answerable 24/24 in all arms, fail +2 (B) / +0 (C). IQ3_XXS: answerable +1, fail +1 / +1 | **PASS** |
| M3 | the effect does not depend on bit depth (C ratio within +/-0.10) | IQ3_XXS **0.773** (p = 0.0076, 11/16 shorter) vs Q6_K 0.858; difference -0.085 | **PASS** (within tolerance) |
| M4 | the model substitutes: penalized markers fall >= 90 %, substitutes >= 2x | markers **-95 %**; substitutes (lowercase wait/hmm/however/alternatively/actually, "let me reconsider", "on second thought") 1.7x, from 0.027 to 0.045 per 1k chars | **FAIL** (little substitution into those forms) |

M4's rates per 1,000 reasoning characters, pooled over both models, are the scorer's operationalization of "fall" and
"double". The prereg did not fix the normalization.

**Reading, applied as registered:** M1 false -> "this model routes around a token-level penalty (M4 says how)". M4
says it does **not** route through the obvious substitutes. The penalty removes the markers and deliberation shortens
a little, but at Q6_K not enough, or not consistently enough, to clear the registered bar on 16 items.

## Descriptive (not registered)

- **The shortening is concentrated on the unanswerable half, and is similar in both models:** arm C unanswerable-only
  ratio Q6_K 0.74 (p = 0.34, 6/8 shorter), IQ3_XXS 0.71 (p = 0.039, 6/8). Answerable items are short in every arm
  (median ~750 chars).
- **The penalty removes IQ3_XXS's excess thinking.** Per item, IQ3_XXS thinks 1.12x Q6_K in arm A (p = 0.34), 1.10x
  in B, and **1.007x in C**. Total completion tokens fall 20 % at Q6_K and 40 % at IQ3_XXS, the larger drop coming off
  the larger baseline.
- **This is consistent with the KLD receipt:**
  - both models respond by a similar relative amount on the items where deliberation lives, so there is no sign of a
    quantization-specific marker weakness;
  - the larger absolute saving at IQ3_XXS comes from its larger baseline, not a larger relative effect.

## What it means

- **Safe but unproven at Q6_K.** Calibration is untouched (answerable 24/24 in every Q6_K arm). The length saving
  at Q6_K (~14 % per item, ~20 % of tokens) is not established on 16 items. For a low-bit quant (IQ3_XXS) it is
  real here: 23 % per item, 40 % of tokens.
- **Deployment would be cheap:** the wake proxy could add `logit_bias` to requests. It is not worth doing for the
  Q6_K daily driver on this evidence. It would be for a low-bit model, or if a larger item set confirms the Q6_K
  effect.
- The source reported 12-23 % shorter CoT across 5 models. Our Q6_K point estimate (14 %) sits in that range; we just
  cannot distinguish it from noise with 16 items.

## Not established

- 16 items (a gate-sized set), `xhigh` only (Mark's daily effort is now `medium`, where thinking is shorter anyway),
  lambda at 2 and 4, one model family.
- IQ3_XXS is the earlier Unsloth upload (see `quant-hesitation/`, Arm provenance).
- No answer-quality measure beyond the CAL grading.
