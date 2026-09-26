# The marker penalty on Bonsai 2: it trims the long tail (0.54x the tokens, runaways 3 -> 0) but misses the registered per-item bar (0.798, p = 0.076); and Bonsai confabulates on three items where Qwen quants abstain

**2026-09-25**, .194 as two 2-GPU testers.
- **Binary:** PrismML fork `9a9394a` (sm_60).
- **Model:** `Ternary-Bonsai-2-27B-PQ2_0.gguf` (sha256 `3907dc1658db1f78...`).
- **Settings:** `-sm layer` (Deviation 1), CAL tier, `--effort xhigh`, 3 reps, 16 items, arms A (no penalty) / B (-2) /
  C (-4) on 20 marker tokens.
- **Prereg:** `PREREG_MARKER_PENALTY_BONSAI.md` (+ Deviations 1-2).
- **Raw:** `raw/out_bonsai1`, `raw/out_bonsai2` (items split by tester), `raw/bonsai/logs/`.
- **Scorer:** `analyze_marker_bonsai.py` produces `RESULT_marker_bonsai.json` for the registered statistics. The
  matched and true-token numbers below were computed from the same raw rows.

Every item's three arms ran on one tester. 144/144 rows, with no duplicates (asserted).

## Predictions

| # | claim | result | verdict |
|---|---|---|---|
| B1 | C shortens thinking: per-item geometric ratio < 0.80 and exact sign-flip p < 0.05 | **0.798, p = 0.076** (8/16 items shorter) | **false** (the ratio clears the bar; the test does not) |
| B2 | C cuts runaways (NO-STOP count C < A; descriptive) | **A 3 -> C 0** (B: 1) | held (descriptive) |
| B3 | no calibration cost: answerable >= A - 2, unanswerable fail <= A + 2 | answerable 23 -> 23; unanswerable fail 10 -> 9 | **held** |
| B4 | the source's accuracy gain: answerable C >= A + 2 | 23 -> 23 | false, **and untestable**: A was already 23/24, so +2 was impossible. The prediction was mis-specified |

## Tokens: count every attempt, and compare matched pairs

**Two corrections to the naive totals, both of which matter here:**
- **Count every attempt.** The CAL runner retries a run that hits 6,144 tokens with a 12,288 budget, and
  `completion_tokens` records only the final attempt. True cost = the spent budget of every capped attempt + the
  final attempt's tokens.
- **Compare matched pairs.** Totals over "uncapped rows" compare different (item, rep) pairs across arms. The
  honest comparison drops every pair that capped in *any* arm from *all* arms. Four pairs capped: CAL-U2 rep 3,
  CAL-U5 reps 2-3 (in A) and CAL-U4 rep 3 (in B).

| arm | true tokens, all 48 | 44 matched pairs | the 4 capped pairs | retried rows | NO-STOP |
|---|---:|---:|---:|---:|---:|
| A | 118,366 | 60,516 | 57,850 | 5 | 3 |
| B (-2) | 78,403 (0.66x) | 37,808 (0.62x) | 40,595 | 3 | 1 |
| C (-4) | **64,499 (0.54x)** | **26,041 (0.43x)** | 38,458 | 2 | **0** |

**Per-item ratio with the 4 capped pairs dropped from every arm (sensitivity):**

| arm vs A | ratio | exact p | items shorter |
|---|---:|---:|---:|
| C | **0.716** | 0.059 | 8/16 |
| B | 0.751 | 0.038 | 10/16 |

The unmatched "drop `finish == length` rows" version (C 0.875, p = 0.38) is kept in `RESULT_marker_bonsai.json`
for comparability with the Q6_K receipt, which used that method. It drops A's long runs while keeping C's run on the
same pairs, so it understates the effect.

**Reading:**
- **The penalty shortens Bonsai's thinking, mostly by trimming the long tail.** Runs that needed the escalated
  retry: A 5, B 3, C 2. Runs that hit the cap: A 3, B 1, C 0. The median item barely moves; answerable items are
  short in every arm.
- **It does not reach the registered bar.** B1 is false as registered (p = 0.076). The matched sensitivity is
  borderline for C (p = 0.059), and B's p = 0.038 is an unregistered arm.
- **Where A's runaways went,** read pair by pair: in C, CAL-U2 rep 3 abstained, and CAL-U5 reps 2 and 3 answered
  wrong. The CAL-U5 rep 2 run used 11,382 tokens and stopped just under the cap. CAL-U5 is an item Bonsai either
  loops on or answers wrong (A: 1 wrong + 2 capped; B and C: 3 wrong each). The penalty turned the loops into wrong
  answers there, not abstentions.
- **Per-item effects are noisy between the two penalty strengths.**
  - CAL-U6: 0.36 under B, 1.07 under C.
  - CAL-U4: 1.30 under B, 0.40 under C.

**On buun's hypothesis ("the hesitation marker might fix" Bonsai's need for low or no thinking):**
- At `xhigh`, the -4 penalty removed every capped runaway in this sample and cut the true token cost to 0.54x.
- It did not change the answers: 23/24 answerable, and 14-15 abstentions on unanswerable items, in every arm.
- For an agent, where a runaway is 12k+ tokens of latency, that is a real saving at no measured accuracy cost. But
  n = 16 items, and the registered test missed.

## Bonsai's calibration: three items, not everywhere

Descriptive, cross-model, arm A, unanswerable items. The Q6_K and IQ3_XXS runs used `-sm tensor` and Bonsai used
`-sm layer`, on the same 2-GPU testers.

| model (arm A, xhigh) | abstained | wrong | NO-STOP | where the wrong answers are |
|---|---:|---:|---:|---|
| Qwen3.8-27B Q6_K | 20 | 3 | 1 | all on CAL-U3 |
| Qwen3.8-27B IQ3_XXS | 23 | 1 | 0 | CAL-U3 |
| **Bonsai 2 PQ2_0** | **14** | **7** | **3** | CAL-U3 x3, **CAL-U6 x2, CAL-U4 x1, CAL-U5 x1** (+ 2 capped on U5) |

- **CAL-U3** ("which year did Mendeleev win the Nobel") gets "1906" from every model. It is the known shared false
  belief (INDEX L58).
- **Beyond it, Bonsai confabulates or loops on three items** (U4, U5, U6) where both Qwen quants abstain: 4 wrong
  answers and 2 runaways that Qwen does not produce.
- Answerable knowledge is intact (23/24).

So Bonsai does not follow the AD ladder's pattern (INDEX L148: quantisation degrades knowledge before calibration).
That ladder was one packager and one method; this is a cross-method comparison on three items, so it is a pointer,
not a law. The penalty moves none of it: 14 abstentions in A, 15 in C.

**Why this matters for a Bonsai front-end that escalates to .73.** On these items, Bonsai's weakness is saying "I
don't know" when it should. So its willingness to ask cannot be the escalation signal. Whether its token
probabilities carry the uncertainty that its answers don't is a separate, measurable question, and the next test.

## Deviations

- **Deviation 1** (in the prereg): `-sm layer`, because prism aborts under tensor split on ternary tensors.
- **Deviation 2:** the prereg says the 20 marker token ids were "verified at launch"; the chain script did not do
  it. They were verified **during the run, before any scoring**, on both serving instances:
  - `/detokenize [id]` returns the expected string;
  - `/tokenize` of the string returns exactly `[id]`;
  - 20/20 match on :8096 and on :8097 (`raw/bonsai/TOKENIZER_CHECK.txt`).

## Correction history

The first version of this receipt (commit `8311d6b`) said "all of the 40 % saving is the three capped runs; on
uncapped rows C is 3 % longer". That was wrong on two counts:
- it compared A's 45 uncapped rows with all 48 of C's, including C's runs on A's capped pairs;
- it counted only final attempts.

The matched comparison above replaces it.

## Not established

- 16 items x 3 reps, `xhigh` only, one very-low-bit model.
- NO-STOP is 3/48 vs 0/48, too few to test.
- The cross-model calibration rows are descriptive: 3 items, a different split mode.
- PQ2_0 is used as a stand-in for PTQ1_0 (they agree to 3.2e-5 KLD per the lowbit-ladder receipt).
