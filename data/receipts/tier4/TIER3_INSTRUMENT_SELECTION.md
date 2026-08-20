# Tier 3 — choosing an instrument that can actually resolve a quant difference

**2026-08-20.** Supersedes the working assumption that HumanEval+ is the tier-3 quality
instrument.

## HumanEval+ is already unable to do the job

Measured on this fleet (`data/receipts/humaneval-plus/`):

| run | pooled pass@1 |
|---|---|
| Laguna-S-2.1 Q2, thinking-on | **90.85 %** |
| Laguna-S-2.1 Q2, thinking-off | 88.01 % |
| Laguna-S-2.1 Q2, t0.6 no-think | 88.21 % |
| Puzzle-75B-A9B (referenced) | 93.90 % |

164 items. At p≈0.91 the 95 % CI on a single measurement is **±4.4 %**, so Laguna Q2
(88.0 ± 5.0) and Puzzle-75B (93.9 ± 3.7) **overlap**. The entire observed spread between a
2-bit model and a 75B is **5.9 points — 2.6 standard errors end to end.** Adjacent models sit
well under one.

## The real criterion is not difficulty

Comparing two quants of the *same* model is a **paired** problem, and paired power comes only
from items where the two disagree. Sample size for McNemar at α=0.05, 80 % power:

| discordant split | discordant pairs needed | items @10 % disagreement | @15 % | @25 % |
|---|---:|---:|---:|---:|
| 60:40 | 194 | 1,936 | 1,291 | 775 |
| 65:35 | 85 | 847 | 565 | 339 |
| **70:30** | **47** | **466** | **311** | **186** |
| 75:25 | 29 | 289 | 193 | 116 |
| 80:20 | 19 | 192 | 128 | 77 |

**HumanEval+ gives ~164 items at ~92 % agreement → about 13 discordant pairs.** No statistical
method recovers that. It is not a difficulty problem; it is an
**items × disagreement** problem, and no amount of harder prompts fixes a short item list.

> **Discriminating power = disagreement rate × item count.** Difficulty only matters insofar
> as it produces disagreement, and a benchmark can be hard *and* useless if both models fail
> the same items (see CritPt: everything outside the top ten sits at 0–3 %).

## Selection criteria for a tier-3 instrument

1. **Non-monotonic in parameter count.** If the leaderboard ranks by model size it tells the
   reader what the file size already told them. The tell is a small model placing high —
   Qwen3.8-27B at #7 on the AA Agentic Index means something other than scale is being measured.
2. **≥ ~300 paired items**, so a 70:30 split is resolvable at realistic disagreement rates.
3. **Not saturated for the class under test** — both arms well away from 100 %.
4. **Relevant to local agentic deployment**: tool calling, long context, instruction
   adherence, calibration. Not closed-book knowledge, which is parameter-bound and where a
   27B is structurally guaranteed to lose.

## BFCL is the instrument, and it is already on disk

`data/receipts/bfcl/` — `bfcl_eval_data_non_live.csv`, `build_bfcl_subset.py`, and
**`bfcl_mcnemar.py`, a paired matched-item test that is exactly the right statistic.**

As actually run for DS4-Flash: **400 items**, scoring **51.5 %** (`parallel`) and **17.0 %**
(`parallel_multiple`). Real dynamic range, nowhere near saturation, squarely in the
resolvable zone at 10–15 % disagreement.

Caveat carried from `DS4_FLASH_IQ1S_W3_MATCHED.md`: that harness **ignored the subset file and
ran the full 200 per category**. Any comparison must confirm the item set actually used before
the numbers are treated as matched — the tell there was that neither score was a multiple of
1/35.

## What this does not settle

- **`parallel_multiple` at 17 % may be too hard** to contribute discordant pairs usefully;
  worth checking per-category before pooling.
- **No fidelity axis.** BFCL scores structural correctness of calls, not answer quality.
- **Calibration is unmeasured.** The AA data suggests non-hallucination is this model class's
  strongest suit; nothing in BFCL tests abstention. The `T1-05`-style items with
  `gold=UNKNOWN` in the viability fixture are the seed of that tier and should be expanded.
