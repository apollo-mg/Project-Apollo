# RESULT: Spark-X2.6 knows exactly what 2.5 knew, and is less honest about what it doesn't

**Prereg:** `PREREG_SPARK_25_vs_26.md` (`cce9dfa5`), with the per-model preregs and chains (`82b24953`).

**Run:** 2026-10-29, one sitting on the RX 9070 XT. 2.5 ran 11:20-13:34; 2.6 ran 13:34-16:55, its vendor mode taking 1 h 58 min
against 2.5's 44 min.
- **Shared host state:** kernel 7.3.0-4, amdgpu firmware 20261019, llama.cpp `f74e2fa`.
- **Files:** both official Q8_0, hash-verified.
- **Stages:** every one completed for both models: 240 + 240 M1 rows, 1,000 AbstentionBench rows with 0 errors, and
  1,000 verdicts with 0 unparsed.
- **Sampler defaults:** the defaults embedded in the two files are identical (top_k off, min_p 0.05). They apply to
  AbstentionBench only, the same way for both.

**Numbers:** `RESULT_spark_25_vs_26.json` (`analyze_spark.py`, paired bootstrap 10,000).

## Primary metrics

| metric | 2.5 | 2.6 | 2.6 - 2.5 [95 %] | |
|---|---|---|---|---|
| greedy hard recall | 0.15 | 0.15 | +0.00 [-0.06, +0.06] | no detectable change (E1 holds) |
| greedy refusal of invented items (lenient) | 0.46 | 0.31 | **-0.15 [-0.23, -0.08]** | changed |
| AbstentionBench recall (sub1000) | 0.410 | 0.343 | **-0.066 [-0.117, -0.016]** | changed |
| vendor-mode unfinished (thinking, 8,192 tokens) | 0.033 | 0.175 | **+0.142 [+0.092, +0.196]** | changed |

Three of the four primary metrics moved, all in the same direction:
- **Knowledge is unchanged.** E1 held, and it fits a post-training update over the same base.
- **Less honest when it does not know.** With thinking off, it refuses invented questions less: confabulation rose from
  0.54 to 0.69. On AbstentionBench it abstains less when it should.
- **Less reliable when it thinks.** One answer in six now runs into the cap, against one in thirty.

## Exploratory (about 0.6 false "changed" calls expected among 12)

| metric | 2.5 | 2.6 | diff |
|---|---|---|---|
| AbstentionBench missing-info recall | 0.500 | 0.291 | -0.209 [-0.337, -0.081] |
| vendor refusal of invented items | 0.36 | 0.15 | -0.21 [-0.31, -0.11] |
| vendor hard accuracy | 0.18 | 0.11 | -0.07 [-0.13, -0.02] |

All other exploratory metrics showed no detectable change: AbstentionBench precision and false-premise recall, easy
accuracy, greedy over-abstention, and vendor confabulation.
- **Not only runaways:** the vendor drops survive counting finished answers only. Refusal of invented items is 0.217
  (n = 69) against 0.383 (n = 94); confabulation is 0.77 against 0.62.
- **Longer thinking:** median reasoning per answer is 2,406 characters against 1,523 (+58 %).
- **Why that cannot be separated:** 2.6's template adds a "thinking_effort=high" line by default, so in thinking mode
  this compares the releases as shipped and cannot separate weights from template (stated in the prereg). The
  thinking-off results (greedy, AbstentionBench) have no such line, and show the same direction.

## What it means

- **A point release can trade honesty away with knowledge held fixed.** It is the same pattern as Sage against its
  base. Benchmarks of capability would not see it.
- **For anyone running Spark 2.5 for honest Q&A,** the upgrade is not free. For agentic use, the comparison here is
  silent: M1 and AbstentionBench do not test tools.

## Limits

- One file per release (Q8_0), one host, one sitting.
- **AbstentionBench samplers:** the AbstentionBench runner leaves top_k and min_p to the server, so these two arms ran
  with the files' own defaults (top_k off), unlike the anchors (top_k 40). The 2.5 vs 2.6 comparison is matched; the
  comparison with the anchors is not. Fix proposed in `ROADMAP.md`.
