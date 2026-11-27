# RESULT: Kolibri 1.1 knows twice as many hard facts as Kolibri 1 (53 vs 26 of 100) and declines more invented questions (73 vs 63) -- with 3.4B active parameters it beats Qwen3.8-27B at Q8_0 on both; the jump is the model, not the port

**Prereg:** `PREREG_KOLIBRI11.md` (`0178ed74`, before any M1 row). **Run:** 2026-11-27, .194 (4x P100, 150 W cap), KOL11
17:50-17:59 on llama.cpp PR #32891 `5f4d22289`, KOL1 18:06-18:21 on October's port 1 (Hob-forge `60d1d51cc`); exploratory
KOL1P 18:22-18:30 on the PR build. M1 driven from the desktop, thinking off, greedy, 1,024 tokens. **Records:**
`quant-abstention/raw/main_KOL11.jsonl`, `main_KOL1.jsonl`, `main_KOL1P.jsonl`; `raw/` (state, server, run, smoke, PPL and
KLD logs). **Analysis:** `analyze_k11.py` -> `summary.txt`, `RESULT_k11.json`.

## Checks (before the prereg; details there)

New ops pass on sm_60 (ROUND_NVFP4 4/4, LIGHTNING_INDEXER 240/240, FLASH_ATTN_EXT 4,373/4,373); Kolibri 1.1 on the P100s
vs the CPU, KLD 0.039 / same top 92.2 %, equal to a CPU-vs-CPU path-noise control (0.037 / 93.0 %); file sha256 matches the
Hub.

## Results (M1, bare-answer rule)

| | Kolibri 1 (KOL1, port 1) | Kolibri 1.1 (KOL11) | 1.1 - 1, 95 % CI | Qwen3.8-27B Q8_0 (DR27_N73, context) |
|---|---|---|---|---|
| invented declined (of 100) | 63 | **73** | **+0.10 [+0.02, +0.19]** | 59 |
| invented answered | 37 | **27** | **-0.10 [-0.19, -0.02]** | 39 |
| hard right / wrong / declined | 26 / 59 / 15 | **53** / **37** / 10 | right **+0.27 [+0.17, +0.37]** | 48 / 49 / 3 |
| easy right (of 40) | 30 | 33 | +0.075 [-0.025, +0.175] | 33 |
| unfinished | 0 | 0 | | 2 |
| slot P(UNKNOWN), invented, mean | 0.72 | 0.78 | +0.05 [+0.01, +0.11] | 0.70 |
| median output tokens | 28 | 28 | | 58.5 |

| prediction | result |
|---|---|
| H1 Kolibri 1.1 hard right >= Kolibri 1 (0.6) | **holds:** 53 vs 26 |
| H2 Kolibri 1.1 declines more invented questions (0.55) | **holds:** 73 vs 63 |

## Exploratory: is Kolibri 1's score an artifact of October's unofficial port?

The same Kolibri 1 file on the PR build (Aleph Alpha's own `kolibri1` code, with the overrides it needs: pre-tokenizer
`qwen2`, gating key 5 -> 2), KOL1P: invented declined 63, hard 27 / 59 / 14, easy 30 -- the same grade as port 1 on 233 of
240 items (invented 98, hard 95, easy 40). The port does not explain the gap; the model does. (Its wikitext logits differ
from port 1's, KLD 0.053, same top 91.3 %, comparable to Kolibri 1.1's own CPU-vs-CPU path noise of 0.037.)

## Reading

1. **A real knowledge jump between versions.** Kolibri 1.1 answers 27 more of the 100 hard questions right and gives 22
   fewer wrong answers to them. Its card says 1.1 continued from a Kolibri 1 mid-training checkpoint with about 1T more
   tokens and a knowledge cutoff of June 2026; facts of the kind M1 asks are old, so this is better retention or recall,
   not newer data.
2. **And more careful at the same time.** 10 more invented questions declined, with the same short answers (median 28
   tokens). Unusually, knowing more did not come with answering everything: its hard-question wrong answers fell from 59
   to 37 while declines fell only from 15 to 10.
3. **Small active size, strong result.** With 3.4B parameters active per token it beats Qwen3.8-27B Q8_0 (27B dense) on
   both counts here (53 vs 48 hard right, 73 vs 59 declined); total size is 75B, which is what holds facts.
4. **The vendor measures this too.** Aleph Alpha publishes per-quant hallucination numbers for these files
   (AA-Omniscience hallucination rate 39.1 % at Q4_K_M vs 38.9 % unquantized, rising by 21-54 points at their 1.75-2.25
   bpw quants), the same compression cost we saw in Bonsai 2 (`bonsai25/RESULT_BONSAI25.md`).

## Limits

Thinking off only (default is high reasoning); greedy where the vendor samples at 1.0; one quant (Q4_K_M); two builds,
each validated for its model; M1 is short English factual questions and Kolibri is built for German and English; Kolibri
1.1's outputs depend on arithmetic order (7 % of top tokens flip with CPU thread count), so another build could change some
answers; the Qwen3.8-27B row is another machine and engine.
