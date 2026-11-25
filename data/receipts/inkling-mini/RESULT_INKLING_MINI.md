# RESULT: Inkling-2-Mini at minimal reasoning declines more invented questions than Qwen3.8-27B with thinking off (78 vs 59 of 100) and knows fewer hard facts (33 vs 48), the opposite of its card's warning on the first count; 22 items ran into greedy repetition loops

**Prereg:** `PREREG_INKLING_MINI.md` (`865de541`, before any M1 row; the smoke and the 2-GPU split workaround disclosed
there). **Run:** 2026-11-24 22:18 to 2026-11-25 02:13 EST, .73 (2x P100), llama.cpp mainline `33aeb17f8` (binary
`78d2ddeb...`), `-ts 1,3`, the AtomicChat AD-Q6_K (sha256 `aebacd90...`, checked on .73), `reasoning_effort` "none",
greedy, 4,096 tokens. **Records:** `quant-abstention/raw/main_INK.jsonl`, `raw/state.log`, `raw/server_INK.log`,
`raw/run_INK.log`. **Analysis:** `analyze_ink.py` -> `summary.txt`, `RESULT_ink.json`.

## Results (M1, bare-answer rule; reference DR27_N73 = Qwen3.8-27B Q8_0, same machine and commit, thinking off)

| | Inkling-2-Mini (minimal reasoning) | Qwen3.8-27B (thinking off) | INK - Qwen, 95 % CI |
|---|---|---|---|
| invented questions declined (of 100) | **78** | 59 | **+0.19 [+0.09, +0.29]** |
| invented questions answered | **6** | 39 | |
| hard questions right / wrong / declined | **33** / 43 / 18 | 48 / 49 / 3 | right **-0.15 [-0.27, -0.03]** |
| easy questions right (of 40) | 33 | 33 | 0.00 [-0.10, +0.10] |
| unfinished (ran out of 4,096 tokens) | **22** (16 invented, 6 hard) | 2 | |
| median output tokens (easy / hard / invented) | 150 / 372 / 432 | 59 overall | |
| median decode speed | 15.6 tok/s | 10.8 tok/s | |

| prediction | result |
|---|---|
| H1 INK declines fewer invented questions than Qwen3.8-27B (0.55) | **fails, the other way:** 78 vs 59 -- and it answers 6 invented questions to Qwen's 39 |
| H2a INK knows no more hard facts (hard right at most 48) (0.65) | **holds:** 33 |
| H2b no SenseNova-style collapse (hard right at least 30) (0.7) | **holds:** 33 |

## Reading

1. **More careful than its card suggests, at this setting.** The card warns that Mini states wrong things with confidence
   more than larger models (AA-Omniscience non-hallucination 63.4 % vs Qwen3.8-27B's 71.4 %). On M1 at minimal
   reasoning it made up an answer to 6 invented questions where Qwen thinking-off made up 39, and gave fewer wrong hard
   answers (43 vs 49), while declining 18 real hard questions to Qwen's 3.
2. **But this compares two conditions as well as two models.** Inkling cannot switch reasoning off; "none" still reasons
   a few hundred tokens. Reasoning by itself raises declining a lot on this instrument (Qwen3.5-9B: 0.68 -> 0.94 with
   thinking on, `quant-abstention/RESULT_SAGE.md`), so part or all of the +0.19 may be the reasoning, not the model. The
   card's AA-Omniscience figures are also at another setting and prompt (M1 offers UNKNOWN explicitly).
3. **It knows less.** 33 hard facts right against 48, consistent with the card's own "largest gaps on factual recall"
   and with the loop buying compute rather than stored facts. Unlike SenseNova (14 of 100), no collapse.
4. **Runaway reasoning at greedy decoding.** 22 items hit the 4,096-token cap, all in reasoning, typically a repetition
   loop (M1-H-ope-093: "Maybe by Ambroise Thomas? no." repeated to the cap). The vendor's generation config uses
   temperature 1.0; greedy decoding is this instrument's rule for every arm, and it is likely to provoke these loops.
   Counted as unfinished, neither declined nor answered.
5. **Faster per token, slower per answer.** 15.6 tok/s against the dense 27B's 10.8 on the same cards, but a median of
   ~350 tokens per item against ~60, so the run took four hours instead of one.

## Limits

Minimal reasoning against thinking off (the main confound); greedy only, though the vendor samples at 1.0; one quant
(AD-Q6_K) of a 26B MoE against a 27B dense Q8_0; the 2-GPU split needed `-ts 1,3` (`raw/diag_split.log`); one smoke
question had matched an M1 topic (disclosed in the prereg). A same-condition comparison would need Qwen3.8-27B with
thinking on at a low effort, or a sampled run of both.
