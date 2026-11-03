# RESULT: at matched bytes, the two DeepSeek-V4.1 builds trade calibration for knowledge

**Prereg:** `PREREG_DS41_H2H.md` (`f05e71e1`, before any DS41 row). **Run:** 2026-11-03 02:09-05:29 on .194 (4x P100,
150 W / 1063 MHz), upstream llama.cpp b12063, `run_ds41_arms.sh`; every gate passed (log
`quant-abstention/raw/logs/ds41_arms.log`). **Numbers:** `RESULT_ds41_h2h.json` (`analyze_ds41.py DS41G DS41U --replay ...`).
**Raw:** `quant-abstention/raw/main_DS41G.jsonl`, `main_DS41U.jsonl`, `main_DS41GR.M1R20.jsonl`.

## The result

Two builds of DeepSeek-V4.1-Flash-1017 with the same Engram table (byte-identical), the same tokenizer, prompts that
hash the same, and routed experts within 0.1 % in bytes (132.07 vs 132.21 GB) behave differently on M1:

| | GSQ-RCO "IQ2_XXS" (ISTA) | UD "IQ1_M" (Unsloth) | GSQ - UD [95 % CI] | McNemar p |
|---|---:|---:|---:|---:|
| **invented items refused** | **0.99** | 0.82 | **+0.17** [+0.10, +0.25] | < 0.0001 (17 vs 0) |
| invented items answered (made up) | 0.01 | 0.18 | -0.17 | |
| **hard real items correct** | 0.79 | **0.87** | **-0.08** [-0.15, -0.02] | 0.039 (2 vs 10) |
| hard real items refused | 0.02 | 0.01 | +0.01 | 1.0 |
| easy items correct | 0.925 | 0.975 | -0.05 [-0.125, 0] | 0.5 |
| unfinished | 1 of 240 | 0 | | |

- **GSQ refuses invented items at 0.99,** among the highest on this instrument: Granite 4.1 3B with an "I don't know"
  LoRA reaches 1.00, Reflection Beam 0.97-0.99 across its effort settings, Nemotron 3.5 Super VL 0.92. All 99 end in
  the instructed `Exact Answer: UNKNOWN`.
- **The UD build knows more:** 0.87 on hard items, near the top of M1 (Reflection Beam 0.88-0.89, Super VL 0.86,
  Flash-Next GSQ IQ3_XXS 0.83). Its extra hits are real recall (a regional capital, a district capital, a publication
  year).
- **Its misses on invented items are confident fabrications:** invented operas get named composers, librettists and
  premiere years.
- **GSQ's lower hard accuracy is wrong answers (18), not timidity (2 refusals).**
- **Grades agree on 0.87 of items.** The replay of 20 DS41G items on a fresh server is byte-identical on all 20.

## Predictions

| # | claim | result |
|---|---|---|
| P1 | no detectable knowledge difference | **FAILED:** -0.08, p = 0.039 |
| P2 | no detectable calibration difference | **FAILED:** +0.17, p < 0.0001 |
| P3 | both arms at or above Flash-Next Q2's 0.79 on hard items | **held:** 0.79 and 0.87 (GSQ exactly at the bar) |
| P4 | a fresh server reproduces the arm | **held:** 20 of 20 byte-identical |

## What this does and does not show

- **Matched bytes do not mean matched behaviour.** The builds differ only in how the backbone's bytes are allocated, and
  that moved calibration by 17 points and knowledge by 8, in opposite directions.
- **The vendors' numbers cannot see this.** ISTA reports 100.0 % recovery on AIME25, GPQA-Diamond and LiveCodeBench at
  reasoning effort 50. None of those measures whether a model invents an answer to a question about something that
  does not exist.
- **Which build is closer to the base model is not known.** The base needs about 1.5 TB and was not run. GSQ may have
  kept the base's calibration while UD lost it, or GSQ may refuse more than the base does. Only the difference between
  the two builds is measured.
- **One model, two specific files, thinking off, greedy, n = 100 per group.** It does not show that GSQ-RCO or Unsloth's
  dynamic method behaves this way on other models.
- **Speed** (recorded, not claimed): warm decode medians 6.5 t/s (GSQ) and 5.8 t/s (UD); mean 15 s and 24 s per item.
  The smoke tests' 2 t/s were a cold page cache.

## Instrument notes

- Thinking off, so this measures the direct answer. ISTA's card numbers use thinking at effort 50.
- The forced-slot P(UNKNOWN) was not collected (" UNKNOWN" is not one token in this tokenizer; registered).
- Server defaults differ between the files (GSQ: llama.cpp's T 0.8 / top_p 0.95; UD's metadata: T 1.0 / top_p 1.0).
  Every request was greedy with neutral penalties sent explicitly, so neither default applied.
