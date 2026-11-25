# RESULT: SenseNova-Loop-9B's loop count works like a caution dial, not a knowledge dial -- a third loop declines more invented questions (67 vs 53 of 100) with no longer answers, while knowing slightly fewer facts; one loop breaks the model

**Prereg:** `PREREG_LOOP_DIAL.md` (`46df4873`, before any M1 row or reference number at 1 or 3 loops). **Runs:** 2026-11-25:
M1 on the desktop (old PR 32588 `4bc61eed7` binary, ROCm 7.2.4 runtime via `tools/rocm724.sh`, flags as the 11-23 SNL arm),
10:47-11:42; the reference on .194's CPUs, 10:51-11:10. **Records:** `quant-abstention/raw/main_SNL_L1.jsonl`,
`main_SNL_L2R.jsonl`, `main_SNL_L3.jsonl`; `raw/` (state, server and run logs, reference outputs); `rewrite_log.txt`.
**Analysis:** `analyze_dial.py` -> `summary.txt`, `RESULT_dial.json`.

## Gates

- **The files:** `rewrite_loops.py` changes only the header (loop count, block count, per-layer attention list) and renames
  the tail and MTP blocks; at 2 loops it reproduces the original file byte for byte.
- **The replay:** the original file on this setup matched the 11-23 SNL arm, 240 of 240 answers.
- **The port at other counts:** SenseTime's reference implementation (config set to 1 or 3 loops, FP32 CPU, the same 20
  wikitext chunks): **44.21 vs llama.cpp 44.11 at 1 loop, 20.67 vs 20.61 at 3 loops** (both within 0.3 %; at 2 loops,
  17.56 vs 17.54). Both counts accepted.

## Results (M1, greedy, thinking off, bare-answer rule)

| loops | invented declined | invented answered | hard right / wrong / declined | easy right | unfinished | median tokens | decode tok/s | wikitext PPL |
|---|---|---|---|---|---|---|---|---|
| 1 | 58 | 37 | 3 / 79 / 17 | **8** / 40 | 9 | 48 | 34.9 | 44.1 |
| **2 (trained)** | 53 | 47 | 14 / 78 / 7 | 27 / 40 | 2 | 46 | 19.0 | 17.5 |
| 3 | **67** | 32 | 9 / 79 / 11 | 24 / 40 | 2 | 48 | 13.4 | 20.6 |

Against 2 loops (paired bootstrap over items): 3 loops invented declined **+0.14 [+0.05, +0.23]**, hard right
**-0.05 [-0.10, -0.01]**, easy right -0.075 [-0.20, +0.05]; 1 loop invented declined +0.05 [-0.06, +0.16], hard right
-0.11 [-0.18, -0.05], easy right **-0.475 [-0.625, -0.325]**.

| prediction | result |
|---|---|
| D1 one loop knows no more than two (hard right at most 14) (0.7) | **holds:** 3 |
| D2 three loops buy no facts (hard right at most 17) (0.75) | **holds:** 9 |
| D3 declining by loop count (exploratory) | 3 loops: +14 points; 1 loop: no clear change |

## Reading

1. **A third loop makes the model more cautious, not more knowledgeable.** It declines 14 more of the 100 invented
   questions and answers 15 fewer of them, but it also gets 5 fewer hard facts right and declines a few more real
   questions (11 vs 7). The shift is toward "I don't know" across the board, with the same answer length: the extra
   computation happens inside the network, not in visible text.
2. **Depth buys no stored facts.** Consistent with GLM-5.4's ablation (smallest gain on the knowledge-heavy benchmark) and
   with both looped models we have measured knowing less than comparable models.
3. **One loop breaks it.** 8 of 40 easy questions right against 27, perplexity 44 against 17.5: a model trained at two
   passes needs both.
4. **The cost is speed:** 19 -> 13.4 tokens per second for the third pass.

So the loop count can move caution like a reasoning-effort setting does, without spending context. Here, on a model
trained at 2 loops and run at 3, the extra caution also cost some knowledge.

## Limits

One model, trained at 2 loops, so 1 and 3 are off its training distribution; greedy, thinking off; short factual English
questions; one quant; the shift at 3 loops could be partly a general loss of confidence off-distribution rather than
deliberate caution -- the drop in real answers right says it is not free.
