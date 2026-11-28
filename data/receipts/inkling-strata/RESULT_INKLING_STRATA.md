# RESULT: Inkling-2-Mini with its reasoning truly off is exactly as cautious as Qwen3.8-27B (61 vs 59 invented declined) while knowing far fewer facts (29 vs 48 hard right); Strata's SQ-10 pack, "same next word 92 % of the time", collapses into a timid model that answers UNKNOWN to half of everything

**Prereg:** `PREREG_INKLING_STRATA.md` (`dab10efa`, committed before any M1 row). **Run:** 2026-11-27 20:12-20:30 EST, .73
(2x P100), Strata 0.2.23 (Control and Inkling engine 0.1.70, CUDA 12), `--kv fp16`, drafting off, `reasoning_effort` "none",
greedy, 4,096 tokens. **Records:** `quant-abstention/raw/main_INKS20.jsonl`, `main_INKS20V2.jsonl`, `main_INKS10.jsonl`;
`raw/` (state, launch, run and smoke logs). **Analysis:** `analyze_ink_strata.py` -> `summary.txt`, `RESULT_ink_strata.json`.

## Results (M1, bare-answer rule)

| | SQ-20 (INKS20, the release) | SQ-10 (INKS10) | INK (llama.cpp, AtomicChat Q6_K, "none" still reasons) | Qwen3.8-27B Q8_0, thinking off |
|---|---|---|---|---|
| invented declined (of 100) | 61 | **85** | 78 | 59 |
| invented answered | 39 | 15 | 6 (16 unfinished) | 39 |
| hard right / wrong / declined | 29 / 52 / 19 | **12** / 40 / **48** | 33 / 43 / 18 | 48 / 49 / 3 |
| easy right (of 40) | 32 | **26** | 33 | 33 |
| unfinished | 0 | 0 | 22 | 2 |
| median output tokens | 30 | 6 | 350 | 58.5 |

SQv2-20 (INKS20V2, what `--model SQ-20` installs in 0.2.23) gave the same answer text as SQ-20 on 240 of 240 items.

Paired differences (bootstrap over items, 10,000, seed 20261127):
- SQ-10 - SQ-20: invented declined +0.24 [+0.15, +0.33], hard right **-0.17 [-0.25, -0.10]**, hard declined +0.29 [+0.19, +0.39],
  easy right -0.15 [-0.275, -0.05].
- SQ-20 - INK: invented declined **-0.17 [-0.26, -0.08]**, invented answered +0.33 [+0.24, +0.42], hard right -0.04 [-0.10, +0.01].
- SQ-20 - Qwen3.8-27B: invented declined +0.02 [-0.08, +0.12], hard right **-0.19 [-0.30, -0.08]**, hard declined +0.16.

| prediction | result |
|---|---|
| S1 SQ-10 declines fewer invented questions than SQ-20 (0.55) | **fails, the other way:** 85 vs 61 |
| S2 SQ-10 hard right <= SQ-20 (0.65) | **holds:** 12 vs 29 |
| S3 SQ-20, reasoning off, declines fewer invented questions than INK (0.7) | **holds:** 61 vs 78 |

## Reading

1. **The matched comparison the Inkling result was missing.** With reasoning off on both, Inkling-2-Mini declines invented
   questions exactly as often as Qwen3.8-27B (61 vs 59) and makes up exactly as many answers (39 vs 39), but knows 19 fewer
   hard facts. Its earlier caution (78) came from the reasoning that llama.cpp's "none" did not switch off.
2. **SQ-10 is a different model in behaviour.** Strata's measure (same next word 92.35 % of the time on held-out prompts)
   sounds close, but on M1 the pack answers a bare "Exact Answer: UNKNOWN" on 124 of 240 items, declines 48 real hard
   questions (SQ-20: 19), drops hard right from 29 to 12 and easy right from 32 to 26 (Iraq's Babylon Governorate: SQ-20
   "Hillah", SQ-10 "UNKNOWN"). Its 85 invented declines are timidity, not honesty: it declines nearly everything it is not
   sure of, and it is sure of much less.
3. **The lossless pack is what the card says.** SQ-20 and Strata's newer default SQv2-20 answer identically on all 240.
4. **Speed, same cards:** ~42 tok/s on Strata (smoke) against 15.6 for llama.cpp on the AtomicChat Q6_K (different file and
   reasoning setting, so indicative only).

## Limits

Reasoning off only; greedy where the vendor samples at 1.0; INK differs from INKS20 in engine, file and reasoning, so S3 is
not a file test; the file test is SQ-20 vs SQ-10 within Strata; one run per arm; M1 is short English factual questions.
