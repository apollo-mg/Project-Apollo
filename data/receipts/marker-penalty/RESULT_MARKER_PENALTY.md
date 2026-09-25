# A logit penalty on 20 hesitation-marker tokens costs no calibration, but shortens Qwen3.8-27B's thinking only modestly: 0.77x at IQ3_XXS (p = 0.008, unregistered), 0.86x at Q6_K (p = 0.32; 0.93x without one capped run)

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

- **IQ3_XXS arm C (0.773, p = 0.0076) is one of four unregistered comparisons** (2 models x 2 arms; M1 registered
  Q6_K only). It survives a 4-way Bonferroni correction (0.03).
- **Sensitivity to NO-STOP.** The CAL tier reports truncated replies separately, and Q6_K arms A and B each contain
  one capped 6,144-token run.
  - Excluding `finish == length` rows, Q6_K's per-item ratio is **0.93 (C, p = 0.65)** and 0.90 (B, p = 0.48).
  - IQ3_XXS has no capped runs and is unchanged.
  - So **the Q6_K per-item effect is 7-14 %, depending on one run.**
- **Totals and outliers.** Completion tokens fall 20 % (C) at Q6_K, and 25 % without its largest item (CAL-U4,
  14,646 of 52,625 arm-A tokens). At IQ3_XXS they fall 40 %, and 36 % without CAL-U2 (24,303 of 71,520). Both hold up.
- **The shortening is concentrated on the unanswerable half, and is similar in both models:** arm C unanswerable-only
  ratio Q6_K 0.74 (p = 0.34, 6/8 shorter), IQ3_XXS 0.71 (p = 0.039, 6/8). Answerable items are short in every arm
  (median ~750 chars).
- **IQ3_XXS vs Q6_K thinking, per item:** 1.12x in arm A (p = 0.34, **not significant**), 1.10x in B, 1.007x in C.
  Descriptive only: no baseline excess is established, so none is claimed removed.
- **Relation to the KLD receipt:**
  - On the registered per-item ratio, IQ3_XXS responds *more* than Q6_K (0.77 vs 0.86). That is inside M3's
    tolerance, but the lean is real.
  - On the unanswerable items, where the deliberation is, the two are similar (0.71 vs 0.74).
  - There is no evidence of a quantization-specific marker effect, but a lean toward the low-bit model is noted, and a
    larger item set could separate it.

## What it means

- **Safe but unproven at Q6_K.** Calibration is untouched (answerable 24/24 in every Q6_K arm). The Q6_K saving
  (7-14 % per item, depending on one capped run; 20-25 % of tokens) is not established on 16 items. At IQ3_XXS the
  per-item effect is clearer (23 %, p = 0.008, unregistered but surviving correction; 36-40 % of tokens).
- **Deployment would be cheap:** the wake proxy could add `logit_bias` to requests. It is not worth doing for the
  Q6_K daily driver on this evidence. It would be for a low-bit model, or if a larger item set confirms the Q6_K
  effect.
- The source reported 12-23 % shorter CoT across 5 models. Our Q6_K per-item estimate (7-14 %) is at or below that
  range and cannot be distinguished from noise with 16 items.

## Not established

- 16 items (a gate-sized set), `xhigh` only (Mark's recent Hermes sessions used `medium`, though his config still says `xhigh`),
  lambda at 2 and 4, one model family.
- IQ3_XXS is the earlier Unsloth upload (see `quant-hesitation/`, Arm provenance).
- No answer-quality measure beyond the CAL grading.
