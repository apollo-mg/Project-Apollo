# The marker penalty on Bonsai 2: it may stop the runaways (3 capped runs -> 0), but it does not shorten Bonsai's thinking, and Bonsai's weak spot is calibration, not loops

**2026-09-25**, .194 as two 2-GPU testers.
- **Binary:** PrismML fork `9a9394a` (sm_60).
- **Model:** `Ternary-Bonsai-2-27B-PQ2_0.gguf` (sha256 `3907dc1658db1f78...`).
- **Settings:** `-sm layer` (Deviation 1), CAL tier, `--effort xhigh`, 3 reps, 16 items, arms A (no penalty) / B (-2) /
  C (-4) on 20 marker tokens.
- **Prereg:** `PREREG_MARKER_PENALTY_BONSAI.md` (+ Deviations 1-2).
- **Raw:** `raw/out_bonsai1`, `raw/out_bonsai2` (items split by tester), `raw/bonsai/logs/`.
- **Scorer:** `analyze_marker_bonsai.py` produces `RESULT_marker_bonsai.json`.

Every item's three arms ran on one tester. 144/144 rows, with no duplicates (asserted).

## Predictions

| # | claim | result | verdict |
|---|---|---|---|
| B1 | C shortens thinking: per-item geometric ratio < 0.80 and exact sign-flip p < 0.05 | **0.798, p = 0.076** (8/16 items shorter) | **false** (the ratio clears the bar; the test does not) |
| B2 | C cuts runaways (NO-STOP count C < A; descriptive) | **A 3 -> C 0** (B: 1) | held (descriptive) |
| B3 | no calibration cost: answerable >= A - 2, unanswerable fail <= A + 2 | answerable 23 -> 23; unanswerable fail 10 -> 9 | **held** |
| B4 | the source's accuracy gain: answerable C >= A + 2 | 23 -> 23 | false, **and untestable**: A was already 23/24, so +2 was impossible. The prediction was mis-specified |

| arm | answerable correct | unanswerable abstained / wrong / NO-STOP | NO-STOP tokens | tokens in uncapped rows | total tokens |
|---|---:|---:|---:|---:|---:|
| A | 23 / 24 | 14 / 7 / 3 | 36,864 | 50,782 | 87,646 |
| B (-2) | 23 / 24 | 14 / 9 / 1 | 12,288 | 47,683 | 59,971 |
| C (-4) | 23 / 24 | 15 / 9 / 0 | 0 | 52,211 | 52,211 |

## What the penalty did and did not do

- **All of the 40 % token saving is the three capped runs.** A's 3 NO-STOP runs (CAL-U2 rep 3, CAL-U5 reps 2-3) hit
  the 12,288-token escalated cap and are 36,864 of its 87,646 tokens. On uncapped rows, C is **3 % longer** than A
  (52,211 vs 50,782).
- **Without the capped rows, the per-item effect is gone:** ratio **0.875, p = 0.38** (the sensitivity the previous
  receipt also reported).
- **The runaways did stop:** 3 -> 0 capped runs in C, 3 -> 1 in B. That is 3/48 vs 0/48, which is not
  significant on its own (the prereg registered B2 as descriptive for this reason).
  - Where the loops went: of A's 3 runaways on unanswerable items, C's counts show +1 abstention and +2 wrong
    answers. The penalty ended the loop but did not make it end *well*.
  - The loop is still there in C: CAL-U5's longest run reached 11,382 tokens and stopped just under the cap.
- **Per-item effects are noisy and inconsistent between the two penalty strengths.**
  - CAL-U6: 0.36 under B, 1.07 under C.
  - CAL-U4: 1.30 under B, 0.40 under C.

  Three reps of a long-tailed length distribution cannot place single items.
- **Unanswerable-only** (unregistered, descriptive): ratio 0.62 (B 0.60), exact p = 0.063 over 8 items, 5/8
  shorter. This is the same concentration on the unanswerable half as the Q6_K/IQ3_XXS run.

**On buun's hypothesis ("the hesitation marker might fix" Bonsai's need for low or no thinking):** partly.
- At `xhigh` the penalty removed every capped runaway in this sample (3 -> 0).
- It did not shorten the thinking otherwise.
- It did not turn loops into abstentions: 2 of the 3 became wrong answers.
- Whether "ends the loop" beats "ends the loop correctly" depends on what a capped run costs you. In an agent, a
  runaway is 12k tokens of latency, so ending it is a real saving even when the answer is no better.

## The finding that matters more: Bonsai's calibration

Descriptive, cross-model, arm A. The Q6_K and IQ3_XXS runs used `-sm tensor` and Bonsai used `-sm layer`, on the
same 2-GPU testers.

| model (arm A, xhigh) | answerable correct | unanswerable abstained | unanswerable wrong | NO-STOP | total tokens |
|---|---:|---:|---:|---:|---:|
| Qwen3.8-27B Q6_K | 24 | 20 | 3 | 1 | 52,625 |
| Qwen3.8-27B IQ3_XXS | 23 | 23 | 1 | 0 | 71,520 |
| **Bonsai 2 PQ2_0** | **23** | **14** | **7** | **3** | 87,646 |

Bonsai 2 keeps its **knowledge** (23/24 answerable, like the Qwen quants) but loses its **calibration**. It answers
7 of the 24 unanswerable items with a confident wrong answer, where the Qwen quants give 1-3.

This is the opposite of the AD-ladder pattern (INDEX L148: quantisation degrades knowledge before calibration, and
IQ2_XS abstains 24/24). Ternary Bonsai breaks it. The marker penalty moves none of this: 14 abstentions in A, 15 in C.

**Why this matters for a Bonsai front-end that escalates to .73.** The escalation signal cannot be Bonsai's own
willingness to say "I don't know", because that is exactly what it lacks here. Whether its token probabilities carry
the uncertainty that its answers don't is a separate, measurable question. That is the next test.

## Deviations

- **Deviation 1** (in the prereg): `-sm layer`, because prism aborts under tensor split on ternary tensors.
- **Deviation 2:** the prereg says the 20 marker token ids were "verified at launch"; the chain script did not do
  it. They were verified **during the run, before any scoring**, on both serving instances:
  - `/detokenize [id]` returns the expected string;
  - `/tokenize` of the string returns exactly `[id]`;
  - 20/20 match on :8096 and on :8097 (`raw/bonsai/TOKENIZER_CHECK.txt`).

## Not established

- 16 items x 3 reps, `xhigh` only, one very-low-bit model.
- NO-STOP is 3/48 vs 0/48, too few to test.
- Cross-model rows are descriptive: different split mode, and different KV quantization history.
- PQ2_0 is used as a stand-in for PTQ1_0 (they agree to 3.2e-5 KLD per the lowbit-ladder receipt).
