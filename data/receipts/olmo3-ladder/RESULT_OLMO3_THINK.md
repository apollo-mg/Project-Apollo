# RESULT: on Olmo 3 7B's reasoning branch, every training stage made the model more careful -- invented questions declined 27 -> 53 -> 73 of 100 -- and the RL stage did it by turning wrong answers into "UNKNOWN" without losing right ones; on the Instruct branch the same RL stage changed nothing

**Prereg:** `PREREG_OLMO3_THINK.md` (`a55157df`, before any M1 row; the first launch failed on a script bug before any row,
`raw/think_attempt0/`, fixed in the next commit). **Run:** 2026-11-25 21:56 to 2026-11-26 04:12 EST, desktop RX 9070 XT,
mainline `33aeb17f8` on ROCm 10.1 with Arch's HIP runtime, Q8_0 of each checkpoint (sha256 in `raw/convert.log`), greedy,
16,384-token cap, `--split-think`. **Records:** `quant-abstention/raw/main_TH_SFT.jsonl`, `main_TH_DPO.jsonl`,
`main_TH_RL.jsonl`; `raw/state_think.log`, server and run logs. **Analysis:** registered `analyze_think.py` ->
`summary_think.txt`, `RESULT_think.json`; registered hedge count `hedge_counts.py --arms TH_SFT TH_DPO TH_RL` ->
`summary_hedge_think.txt` (its "P1/P2" line uses the Instruct prereg's labels and does not apply here); exploratory
`transitions_think.py` (written after the registered results were committed, `e9cb7fd9`) -> `summary_transitions_think.txt`.

## Results (M1, registered bare-answer rule)

| stage | invented declined | invented answered | hard right / wrong / declined | easy right | unfinished | median tokens |
|---|---|---|---|---|---|---|
| Think-SFT | 27 | 48 | 12 / 78 / 2 | 22 / 40 | **34** | 534 |
| + DPO | 53 | 47 | 17 / 74 / 9 | 17 / 40 | 0 | 792 |
| + RL (Think, final) | **73** | **25** | 16 / **53** / **30** | 19 / 40 | 3 | 1,230 |

Unfinished means the 16,384-token cap: every such row is a greedy repetition loop inside the reasoning (one repeats
"Sipaliwini" to the cap). Think-SFT's 34 are 25 invented, 8 hard and 1 easy items.

Paired differences (bootstrap over items, 10,000, seed 20261125):

| | invented declined | invented answered | hard right | hard declined |
|---|---|---|---|---|
| DPO - SFT | **+0.26 [+0.18, +0.35]** | -0.01 [-0.10, +0.08] | +0.05 [0.00, +0.10] | **+0.07 [+0.01, +0.13]** |
| RL - DPO | **+0.20 [+0.11, +0.30]** | **-0.22 [-0.32, -0.13]** | -0.01 [-0.06, +0.04] | **+0.21 [+0.12, +0.31]** |
| RL - SFT | **+0.46 [+0.36, +0.56]** | **-0.23 [-0.33, -0.13]** | +0.04 [-0.01, +0.10] | **+0.28 [+0.19, +0.37]** |

| prediction | result |
|---|---|
| T1 RL moves invented declining by at most 5 points vs DPO (0.5) | **fails:** +20 |
| T2 each Think stage declines more invented questions than its Instruct counterpart (0.7) | **holds** on all three: 27 vs 17, 53 vs 27, 73 vs 29 (Think-SFT minus Instruct-SFT +0.10 [-0.01, +0.21] is not distinguishable from zero; the other two are, +0.26 and +0.44) |
| T3 hard right within 5 between Think-SFT and the final model (0.6) | **holds:** 12 vs 16 (Think-SFT's 12 is undercounted: 8 hard items looped) |

**Registered hedge count:** the Instruct DPO habit (a trailing "UNKNOWN" after an answer) does not recur on this branch:
Think-SFT 0, Think-DPO 4 (all four graded as declines), Think 0.

## Exploratory: where each stage's new declines came from (per item, adjacent stages)

- **SFT -> DPO, invented:** 26 new declines = 15 items that had looped + 11 made-up answers; meanwhile 10 looping items
  became made-up answers. Declining among finished invented items: 27 of 75 (0.36) -> 53 of 100 (0.53). So DPO both
  ended the loops and turned some bluffs into "UNKNOWN".
- **DPO -> RL, invented:** 24 made-up answers became declines, 3 declines became made-up answers.
- **DPO -> RL, hard:** 23 of RL's 24 new declines were questions DPO had answered wrongly (1 was right); 3 right answers
  turned wrong and 3 wrong turned right. RL traded wrong answers for "UNKNOWN", not knowledge.

## Reading

1. **On the reasoning branch, RL made the model much better calibrated.** It cut made-up answers to invented questions
   from 47 to 25 and wrong answers to real hard questions from 74 to 53, putting nearly all of them into "UNKNOWN", while
   the number it knew stayed the same (17 -> 16 hard, 17 -> 19 easy). That is the trade a careful answerer makes.
2. **The same RL stage did nothing on the Instruct branch** (29 vs 27 declined, `RESULT_OLMO3_LADDER.md`). Whether RL
   moves caution depended on the branch it ran on. One candidate mechanism, not tested here: reasoning length grows at
   every Think stage (median 534 -> 792 -> 1,230 tokens), and longer reasoning raises declining on this instrument in
   other models (`inkling-mini/RESULT_Q27_LOW.md`).
3. **DPO helped on both branches,** most here: it ended Think-SFT's runaway loops and moved some bluffs to declines.
4. **No stage added facts.** Hard right 12 / 17 / 16 and easy right 22 / 17 / 19, the same few facts as the Instruct
   branch.
5. **For the RL page's question** ("a model fine-tuned with examples first and RL after: does the drop come back?"):
   here, after SFT and DPO, reasoning RL raised declining by 20 points; on the non-reasoning branch it did not.

## Limits

Think-SFT's own template carries a different default system message from Think-DPO and Think (19 tokens shorter: no
"function-calling" wording or no-functions line, cutoff "December" vs "November 2024"); user prompt and ending are
identical. So SFT -> DPO, and each Think-vs-Instruct pair, also changes the system message; DPO -> RL does not.
Think-SFT's loops (34 rows) cloud its numbers; greedy at the vendor's temperature of 0.6 likely provokes them. One family
at 7B; one quant; a 16,384-token cap; short factual English questions; the transition analysis was written after the
registered results were seen. Tested since (Amendment 1, below): with the DPO template Think-SFT declines the same 27, so the system message is not
what moved SFT -> DPO.

## Amendment 1 result (2026-11-27): the system message did not move SFT -> DPO

`TH_SFT_T` (Think-SFT served with the Think-DPO template; gate: prompt tokens equal TH_DPO's on 240 of 240): invented declined
27 (TH_SFT 27), answered 47, hard 14 / 71 / 5, easy 21, 36 runs to the cap (TH_SFT 34). **A1 holds:** |TH_SFT_T - TH_SFT| =
0.00 [-0.09, +0.09]. Against this matched control, DPO still adds +0.26 [+0.16, +0.36] invented declines. The SFT -> DPO
step is the training, not the default system message; the system-message caveat in Limits is resolved.
Records: `quant-abstention/raw/main_TH_SFT_T.jsonl`, `raw/state_think_t.log`, `summary_think_t.txt`.
