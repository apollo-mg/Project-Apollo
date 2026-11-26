# RESULT: Olmo 3 7B through its training stages -- the RL stage left invented-question declining where DPO put it (29 vs 27 of 100) and added no facts; DPO's largest change was a format habit, writing a separate "UNKNOWN" line after its answer on about half the items, and RL took most of that back out

**Prereg:** `PREREG_OLMO3_LADDER.md` (`6178e251`, before any M1 row; Deviation 1 `511eaaad`, before any complete row).
**Run:** 2026-11-25, desktop RX 9070 XT, mainline `33aeb17f8` on ROCm 10.1 with Arch's HIP runtime
(`tools/rocm101arch.sh`), Q8_0 of each checkpoint (sha256 in `raw/convert.log`), greedy, thinking off; the arms finished
19:26, 19:29 and 19:31 EST (about 64 tok/s, under three minutes per arm). **Records:** `quant-abstention/raw/main_OL_SFT.jsonl`,
`main_OL_DPO.jsonl`, `main_OL_RL.jsonl`; `raw/` (state, server and run logs); the first attempt's partial rows in
`raw/attempt1/`, unread. **Analysis:** registered `analyze_ladder.py` -> `summary.txt`, `RESULT_ladder.json`; exploratory
`hedge_counts.py` (written after the registered analysis was committed, `5fc794c8`) -> `summary_hedge.txt`, `RESULT_hedge.json`.

## Gates

- **Template (Deviation 1):** OL_RL was served with the SFT/DPO template file. Prompt token counts per item are equal
  across all three arms on 240 of 240 items, so the prompts rendered the same.
- **Completeness:** 240 rows per arm, no request errors.

## Results (M1, registered bare-answer rule)

| stage | invented declined | invented answered | hard right / wrong / declined | easy right | no gradable answer | median tokens |
|---|---|---|---|---|---|---|
| SFT (Instruct-SFT) | 17 | 83 | 16 / 69 / 15 | 17 / 40 | 0 | 7 |
| + DPO (Instruct-DPO) | 27 | 69 | 17 / 70 / 10 | 15 / 40 | 10 | 9 |
| + RL (Instruct, final) | 29 | 70 | 16 / 72 / 12 | 17 / 40 | 3 | 7 |

"No gradable answer" here is not running out of tokens: every such row is a few tokens long and gives two answers, e.g.
"Baghdad" on one line and "UNKNOWN" on the next.

Paired differences (bootstrap over items, 10,000, seed 20261125):

| | invented declined | invented answered | hard right | easy right |
|---|---|---|---|---|
| DPO - SFT | +0.10 [-0.02, +0.22] | **-0.14 [-0.26, -0.02]** | +0.01 [-0.04, +0.06] | -0.05 [-0.15, +0.05] |
| RL - DPO | +0.02 [-0.05, +0.09] | +0.01 [-0.07, +0.09] | -0.01 [-0.05, +0.02] | +0.05 [0.00, +0.125] |
| RL - SFT | **+0.12 [+0.02, +0.22]** | **-0.13 [-0.23, -0.03]** | 0.00 [-0.05, +0.05] | 0.00 [-0.075, +0.075] |

| prediction | result |
|---|---|
| P1 RL moves invented declining by at most 5 points vs DPO (0.6) | **holds:** +2 |
| P2 DPO declines fewer invented questions than SFT (0.55) | **fails, the other way:** 27 vs 17 (+0.10, not distinguishable from zero) |
| P3 hard right within 5 between SFT and the final model (0.6) | **holds:** 16 vs 16 |

## Exploratory: the trailing-UNKNOWN habit (not preregistered)

A row "answers then hedges" when its last line is exactly UNKNOWN and an earlier line gives a different answer (most
often "Exact Answer: Daegu" then "UNKNOWN"). The registered grader reads the "Exact Answer" line and ignores the trailing
word, the same way for every arm.

| stage | easy (of 40) | hard (of 100) | invented (of 100) | total |
|---|---|---|---|---|
| SFT | 1 | 1 | 0 | 2 |
| + DPO | **24** (10 of them right) | **54** | **41** | **119** |
| + RL | 4 | 12 | 10 | 26 |

The habit does not track doubt. DPO adds the trailing UNKNOWN to 24 of 40 easy items (10 of them answered correctly),
proportionally more often than to invented ones (41 of 100). If a trailing UNKNOWN counted as declining, invented declining would read 17 /
68 / 39 and P1 would fail. But the same reading would have DPO "declining" 24 easy questions, so it measures the habit,
not caution. The registered reading stands, and the habit is reported here as what DPO changed most.

## Reading

1. **RL after SFT and DPO changed little on this test.** Declining, wrong answers and facts known all moved by at most 2
   points, consistent with RL changing what its reward covers (math, code, instruction following) and little else. It
   did not bring back or remove caution. Across the whole pipeline, SFT to final, the model declines 12 more invented
   questions (+0.12, the one clear shift), most of it arriving at the DPO stage.
2. **The DPO stage's biggest visible effect was a format habit.** Preference tuning taught the model to tack "UNKNOWN"
   onto half its answers, right or wrong; the RL stage, whose reward includes instruction following, removed most of it
   (119 -> 26). Anyone scoring a DPO checkpoint with a strict format parser would see a different model.
3. **No stage adds facts.** Hard right 16, 17, 16 of 100; easy right 17, 15, 17 of 40. At 7B Olmo 3 knows few of M1's
   facts and declines few invented questions (17-29 of 100, against Qwen3.5-9B's 68 thinking off).

## Observations, not scored (from the smoke, disclosed in the prereg)

- **RL-Zero-General** (RL straight from the base, no SFT, an LM-judge reward on general chat) never ends its turn under
  M1's prompt: it answers and then keeps writing to the token cap.
- **The base model** cannot follow M1's answer format and repeats the instructions back.
So without the supervised stage, neither the base nor RL alone produces a model this test can score.

## Limits

No base anchor, so this measures what DPO and RL changed after SFT, not what SFT did to the base. One family at 7B; greedy,
thinking off; one quant (Q8_0); M1 is short factual English questions. Hard right sits at 16-17 of 100, a low base, so
"no stage adds facts" is weak evidence at this size. The hedge rule was written after the registered results were seen.

## Follow-up (2026-11-26): the reasoning branch (`RESULT_OLMO3_THINK.md`)

Reading 1 holds for the Instruct branch only. On Olmo 3 7B's Think branch the RL stage raised invented-question
declining from 53 to 73 of 100 (+0.20 [+0.11, +0.30]), turning wrong answers into "UNKNOWN" without losing right ones;
DPO raised it from 27 to 53. Whether RL moves caution depended on the branch. The trailing-UNKNOWN habit did not recur
there (4 rows at Think-DPO).
