# Result -- quant-abstention INCTX: in generation the decision is made in the sentence the model writes. After it, P(UNKNOWN) is 0 or 1 and every model reads it the same way, so a quant's shift is in what it writes. Four of the five "confident" forced-slot shifts are not in what those files write; AD IQ3_XXS writes more refusals and Bonsai writes more confabulations

**2026-09-27.** Pre-registration `PREREG_INCTX.md` (commit `2d7df40`; sign fix `964ea8d`, before any in-context output was
opened). Analysis `analyze_inctx.py` (`e19f417`, committed before any in-context output was opened, self-tested on fake
rows built from main). Output `RESULT_inctx.json`. Raw `raw/inctx_<reader>__<writer>.jsonl`, launcher log
`raw/inctx_lanes.log`, server metadata `raw/logs/inctx_meta_*.json`.

- **Instrument:** as main. `.194`, buun `0b2789f23` sm_60, main flags, f16 KV verified, no MTP/draft line on any
  server, every reader matched Q8_0's render tail and variant ids.
- **Run:** 11:21-15:27, both lanes.
- **Gate:** the greedy token after the cut reproduced the stored generation on **238/238** items for Q8_0 and on every
  item for every arm except one (EXL3 2.5, 239/240). No arm was flagged.

## Registered verdicts

| claim | rule | result |
|---|---|---|
| **H-ctx-confident** (the confident shift is a forced-slot effect) | >= 4 of the 5 confident-labelled files "shrink" (forced minus in-context, 95 % lower bound > 0) | **supported, 4 of 5** (AD IQ2_XS, APEX I-Nano, EXL3 3.0, EXL3 3.5; not AP IQ3_XXS) |
| **H-ctx-rank** (the ranking survives at the decision point) | >= 18 of 20 PTQ arms within +/-0.03 with an interval including 0 | **partial, 17 of 20**, and **uninformative** (see below) |

| file | forced - in context (confab, 95 %) | shrinks |
|---|---|---|
| AD IQ2_XS | +0.230 [+0.151, +0.309] (n 99) | yes |
| AP IQ3_XXS | +0.066 [-0.008, +0.140] (n 98) | no |
| APEX I-Nano | +0.150 [+0.072, +0.229] (n 97) | yes |
| EXL3 3.0 | +0.099 [+0.025, +0.172] (n 99) | yes |
| EXL3 3.5 | +0.126 [+0.054, +0.198] (n 99) | yes |


**Read "supported" as a confirmation, not a replication.** It uses the same items and the same generations as the
forced-vs-generation gap that motivated the prereg (`RESULT_MAIN.md`, Correction). The in-context readout is, in
effect, the generation's own decision, as the probe requires. So this is a preregistered restatement at a soft
readout of a gap already seen in this data. It is not independent evidence.

**H-ctx-rank cannot answer its question.** After the model's sentence, P(UNKNOWN) is saturated: **100 %** of Q8_0's
in-context values are below 0.01 or above 0.99, against 51 % at the forced slot. The in-context within-template AUROC
therefore measures how the saturated tails happen to order, not which items the model knows.
- The three "failures" are AD IQ2_XS +0.072 [+0.009, +0.131], UD IQ3_XXS +0.031 and AP IQ3_S -0.043. AD IQ2_XS's +0.072
  does **not** mean it ranks better: its written decisions moved by only 0.01-0.02.
- For the same reason, Q8_0's in-context ceiling (0.881) against its forced-slot ceiling (0.970) compares a graded score
  with a nearly binary one. It is not evidence that either is the better signal.

## Per file (arm minus Q8_0; the in-context interval is at main's family level, 99.917 %, and 95 % for Bonsai)

Timidity is P_abs on hard items and confabulation is 1 - P_abs on invented items. The forced-slot and generation columns
are from `RESULT_main.json`.

| file | bpw | probe | forced slot tim / con | in context tim / con [con interval] | generation tim / con | label main -> in context |
|---|---:|---:|---|---|---|---|
| GSQ IQ2_XS | 2.50 | 1.000 | +0.223 / -0.085 | +0.082 / +0.042 [-0.071, +0.155] | +0.082 / +0.042 | none -> **none** |
| GSQ IQ2_S | 2.75 | 1.000 | +0.036 / +0.056 | +0.000 / +0.010 [-0.096, +0.116] | +0.000 / +0.010 | none -> **none** |
| AP IQ2_S | 2.75 | 1.000 | +0.165 / -0.074 | +0.048 / +0.029 [-0.105, +0.163] | +0.051 / +0.030 | timid -> **none** |
| UD Q2_K_XL | 2.82 | 1.000 | +0.032 / +0.074 | -0.010 / -0.010 [-0.136, +0.117] | -0.010 / -0.010 | none -> **none** |
| AD IQ2_XS | 2.85 | 1.000 | -0.028 / +0.213 | -0.010 / -0.020 [-0.141, +0.101] | -0.010 / -0.020 | confident -> **none** |
| GSQ IQ3_XXS | 3.00 | 1.000 | +0.105 / -0.005 | +0.040 / +0.050 [-0.040, +0.141] | +0.040 / +0.051 | none -> **none** |
| UD IQ2_M | 3.00 | 1.000 | +0.065 / +0.015 | +0.000 / -0.038 [-0.151, +0.075] | +0.000 / -0.041 | none -> **none** |
| AP IQ3_XXS | 3.09 | 1.000 | +0.017 / +0.076 | -0.000 / +0.010 [-0.117, +0.138] | +0.000 / +0.010 | confident -> **none** |
| APEX I-Nano | 3.21 | 1.000 | -0.000 / +0.113 | -0.000 / -0.036 [-0.137, +0.065] | +0.000 / -0.031 | confident -> **none** |
| AP IQ3_XS | 3.31 | 1.000 | +0.017 / +0.027 | -0.010 / -0.030 [-0.122, +0.062] | -0.010 / -0.030 | none -> **none** |
| AP IQ3_S | 3.47 | 1.000 | +0.062 / -0.050 | +0.010 / -0.000 [-0.100, +0.100] | +0.010 / +0.000 | none -> **none** |
| UD IQ3_XXS | 3.48 | 1.000 | +0.155 / -0.144 | +0.000 / -0.063 [-0.186, +0.060] | +0.000 / -0.062 | timid -> **none** |
| GSQ IQ3_S | 3.50 | 1.000 | +0.013 / +0.021 | -0.020 / -0.010 [-0.126, +0.106] | -0.020 / -0.010 | none -> **none** |
| AD IQ3_XXS | 3.50 | 1.000 | +0.121 / -0.112 | +0.051 / -0.135 [-0.276, +0.006] | +0.051 / -0.135 | timid -> **none** |
| EXL3 2.5 | 3.59 | 0.996 | +0.036 / -0.044 | +0.000 / +0.022 [-0.087, +0.130] | +0.000 / +0.020 | none -> **none** |
| AD IQ3_S-mix | 3.77 | 1.000 | +0.106 / -0.133 | +0.041 / -0.071 [-0.173, +0.031] | +0.041 / -0.071 | timid -> **none** |
| APEX I-Mini | 4.01 | 1.000 | +0.037 / -0.073 | -0.010 / -0.010 [-0.103, +0.082] | -0.010 / -0.010 | timid -> **none** |
| EXL3 3.0 | 4.05 | 1.000 | +0.008 / +0.061 | -0.010 / -0.040 [-0.161, +0.080] | -0.010 / -0.040 | confident -> **none** |
| UD IQ4_XS | 4.13 | 1.000 | +0.024 / -0.031 | +0.010 / +0.010 [-0.095, +0.115] | +0.010 / +0.010 | none -> **none** |
| EXL3 3.5 | 4.50 | 1.000 | -0.001 / +0.054 | -0.020 / -0.071 [-0.184, +0.043] | -0.020 / -0.071 | confident -> **none** |
| Bonsai PTQ1_0 (95 %) | 1.76 | 1.000 | +0.066 / +0.076 | +0.010 / +0.176 [+0.079, +0.273] | +0.010 / +0.149 | mixed -> **confident** |
| Bonsai PQ2_0 (95 %) | 2.14 | 1.000 | +0.066 / +0.077 | +0.010 / +0.176 [+0.079, +0.273] | +0.010 / +0.151 | mixed -> **confident** |

- **The in-context column equals the generation column** to within 0.005 on every PTQ file. After the sentence the
  answer token is copied, so the in-context readout adds almost nothing beyond the written decision. Bonsai differs by
  up to 0.027, because 8 % of its in-context values are not saturated (Q8_0: 0 %).
- **No PTQ file keeps a label at the family level.** AD IQ3_XXS is closest: confabulation -0.135 [-0.276, +0.006].
  **Bonsai** is "confident" at 95 %: confabulation **+0.176 [+0.079, +0.273]**.

## Reading vs writing (invented items, confabulation direction, 95 %)

X(Y) is P_abs when reader X reads writer Y's prose.

| file | n | total C(C) - arm(arm) | reading on Q8_0's prose C(C) - arm(C) | writing C(C) - C(arm) | reading on the arm's prose C(arm) - arm(arm) |
|---|---:|---|---|---|---|
| AD IQ2_XS | 99 | -0.020 [-0.090, +0.050] | +0.000 [+0.000, +0.000] | -0.020 [-0.090, +0.049] | +0.000 [-0.000, +0.001] |
| AP IQ3_XXS | 98 | +0.010 [-0.063, +0.084] | +0.000 [-0.000, +0.000] | +0.010 [-0.063, +0.083] | +0.000 [-0.000, +0.000] |
| APEX I-Nano | 97 | -0.036 [-0.094, +0.022] | -0.000 [-0.000, +0.000] | -0.041 [-0.097, +0.015] | +0.005 [-0.004, +0.014] |
| EXL3 3.0 | 99 | -0.040 [-0.110, +0.029] | -0.000 [-0.000, -0.000] | -0.040 [-0.110, +0.029] | -0.000 [-0.000, -0.000] |
| EXL3 3.5 | 99 | -0.071 [-0.136, -0.005] | -0.000 [-0.000, -0.000] | -0.071 [-0.136, -0.005] | -0.000 [-0.000, -0.000] |
| AD IQ3_XXS | 96 | -0.135 [-0.216, -0.054] | +0.000 [-0.000, +0.000] | -0.135 [-0.217, -0.054] | +0.000 [+0.000, +0.000] |
| Bonsai PTQ1_0 (95 %) | 94 | +0.176 [+0.079, +0.273] | +0.000 [+0.000, +0.001] | +0.189 [+0.093, +0.285] | -0.014 [-0.031, +0.004] |

- **Reading is nil.** Given the same sentence, every file reads it as Q8_0 does: the largest |dP| on Q8_0's prose was
  0.003 (AD IQ2_XS), 0.001 (APEX I-Nano) and 0.004 (Bonsai). **The whole in-context shift is writing.**
  - AD IQ3_XXS writes more refusals: -0.135 [-0.216, -0.054] at 95 %. That is the level at which today's Correction
    said "timid carries partly". At the family level its label is none.
  - EXL3 3.5 writes slightly more refusals (-0.071 [-0.136, -0.005]).
  - Bonsai writes more confabulations (+0.189 [+0.093, +0.285]).
  - The other confident files write like Q8_0.
- **What this shows and what it cannot show.** A zero reading effect largely follows from the design: once a sentence
  says a thing does not exist, or names an answer, the answer token is determined for any competent reader. The finding
  is where the decision sits: **in the sentence, with the answer slot after it a copy step.** The split does not say
  why a quant writes what it writes.

## What this changes

- **The forced slot is a different readout, not a noisy version of generation.** It is the model's answer with
  nothing written first: a "gut" P(UNKNOWN). The quants shift that gut in file-specific directions (`RESULT_MAIN.md`).
  What they *write* moves much less:
  - no confident file writes more answers to invented questions;
  - AD IQ3_XXS writes more refusals;
  - Bonsai writes more confabulations.
- **CALIB's fix cannot act where generation decides.** A logit bias on the answer token meets a P that is already 0 or 1
  once the sentence is written. The CALIB result stays forced-slot only: log-prob confidence scoring and single-token
  answers. A fix for generation would have to act while the sentence is being generated.
- **For quant choice:** on this prompt with thinking off, no PTQ file from 2.5 to 4.5 scored bpw writes measurably more
  confabulations than Q8_0 at the registered level. AD IQ3_XXS writes more refusals (95 %). Bonsai is the outlier.

## Exploratory (not registered; not a finding): the forced-slot score as a hallucination guard

The forced slot's graded P(UNKNOWN) might catch invented questions that the written answer misses. The test: a
threshold on the forced-slot P, set on one half of the items to match the generation's own false-refusal rate on hard
items, scored on the other half. The 200 stratified partitions are cross-fitted, so the threshold never sees the items
it is scored on. "Rule minus written" is the change in how often the file refuses:

```
C.A     held-out: rule minus written, refuse-U +0.110 (partition spread -0.000..+0.250), refuse-H +0.013
AD2XS   held-out: rule minus written, refuse-U +0.041 (partition spread -0.167..+0.231), refuse-H +0.017
AD3XXS  held-out: rule minus written, refuse-U +0.100 (partition spread -0.021..+0.225), refuse-H +0.009
AD3S    held-out: rule minus written, refuse-U +0.202 (partition spread +0.077..+0.292), refuse-H +0.008
UD3XXS  held-out: rule minus written, refuse-U +0.077 (partition spread -0.064..+0.180), refuse-H +0.010
APEXN   held-out: rule minus written, refuse-U +0.025 (partition spread -0.187..+0.250), refuse-H +0.012
EXL30   held-out: rule minus written, refuse-U -0.077 (partition spread -0.192..+0.058), refuse-H +0.011
EXL35   held-out: rule minus written, refuse-U -0.125 (partition spread -0.250..+0.000), refuse-H +0.019
BON2    held-out: rule minus written, refuse-U +0.195 (partition spread -0.061..+0.347), refuse-H +0.011
```

- For most files the rule refuses more invented questions at about +0.01 more false refusals.
- It does worse on both EXL3 files, and the spread across partitions is wide.
- It is a candidate for its own prereg ("forced-slot gut check as a guard before generation"): fresh items, a
  registered threshold rule, and the cost on correct answers counted separately. It is not a result.

## Not established

- **One sample of prose per file:** the greedy generation from main.
- **Swaps covered invented items and 7 files only.**
- **One model, thinking off, one prompt.** With thinking on, the model writes paragraphs before answering; this result
  predicts the decision lives there, but that is untested.
