# RESULT: Sage's drop in "I don't know" survives sampling -- -0.16 under its own recommended sampling, -0.19 greedy

**Prereg:** `PREREG_SAGE_SAMPLED.md` (`18062cb8`, before any row; no deviations). **Run:** 2026-11-11 13:48-15:28 on .194,
`run_sage_sampled.sh`, log `raw/sage_sampled.log`; every gate passed (both files hash-verified in `/dev/shm`, the
token prompt gate identical on both models, `766e6600...`, as in every earlier run of this pair). **Numbers:**
`RESULT_sage_sampled.json` (`analyze_k.py`). **Raw:** `raw/main_Q36BS{1,2,3}.jsonl`, `raw/main_SGQ6S{1,2,3}.jsonl`.

Same files, build and setup as `RESULT_SAGE_MATCHED.md` (both mradermacher static Q6_K, llama.cpp `c7fc509`, 4x P100
layer split, thinking off); the only change is decoding: Sage's recommended sampling (T 1.0, top_p 0.95, top_k 20,
min_p 0, presence 1.5), three replicates with the same per-item seeds for both models. Per item, each rate is the mean
of the three.

## The result

| | Sage, sampled | base, sampled | Sage - base [95 % CI] | greedy (`RESULT_SAGE_MATCHED.md`) |
|---|---:|---:|---:|---:|
| **invented refused** (bare counted) | **0.533** | 0.693 | **-0.160** [-0.220, -0.103] | -0.19 [-0.28, -0.11] |
| invented made up | 0.443 | 0.300 | +0.143 [+0.087, +0.203] | +0.19 |
| hard real correct | 0.547 | 0.617 | -0.070 [-0.133, -0.010] | -0.03 (n.s.) |
| easy correct | 0.892 | 0.933 | -0.042 [-0.125, +0.042] | +0.025 |
| unfinished | 1.4 % | 0.6 % | | |

**Sampling against greedy, within each model:** the base moves +0.023 [-0.040, +0.090] on invented refusal; Sage
+0.053 [-0.020, +0.127]. Sampling also costs Sage some recall (hard -0.093 [-0.157, -0.033]; the base -0.053, n.s.).

## Predictions

| # | claim | result |
|---|---|---|
| P1 | Sage's drop survives sampling (<= -0.10, CI upper < 0) | **held:** -0.160 [-0.220, -0.103] |
| P2 | sampling barely moves the base (\|dU\| <= 0.05) | **held:** +0.023 |
| P3 | sampling barely moves Sage (\|dU\| <= 0.05) | **failed narrowly:** +0.053, CI includes 0 |

## What this adds

- **The disagreement on HF #23 is not about decoding.** Under the very sampling Jorge Leon used, Sage still refuses
  invented questions 16 points less often than its base on M1, against 19 greedy. With sampling ruled out, what is left
  is the question sets (his 30 items: places, dates and character names around literature; ours: 100, of which Sage's
  greedy flips were 14 novels, 5 universities, 2 capitals), sample size, and the stacks (6-bit MLX vs Q6_K llama.cpp).
- **It confirms, on the pair in dispute, the 9B result** (`sci-distill/RESULT_SCI_DISTILL.md` P11): with thinking off,
  greedy against the vendor's sampling barely moves refusal of invented items. Greedy is not what made these numbers.
- Sampling narrows Sage's gap slightly (it refuses a little more and recalls a little less). Neither within-model shift
  is distinguishable from zero on refusal, so three replicates cannot say why.

## Limits

Thinking off, one instrument (M1), three replicates per item, 100 invented items. Requests ran one at a time, as in the
greedy runs.
