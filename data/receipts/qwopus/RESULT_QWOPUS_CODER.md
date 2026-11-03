# RESULT: Qwopus3.8-27B-Coder-Flash knows what its base knows, and makes up more answers about things that do not exist

**Prereg:** `PREREG_QWOPUS_CODER.md` (`2e2c3014`, before any row). **Run:** 2026-11-03 13:30-14:20 on .194, buun `0b2789f23`,
QWC on GPUs 0+1 and the base replay C.R on GPUs 2+3 at the same time (`run_qwopus.sh`; log
`quant-abstention/raw/logs/qwopus.log`). The first launch stopped at the runner's render-tail gate on both lanes
before writing any row: the driver's `$(cat)` stripped the tail's trailing newlines (fixed in `02b2e8aa`; no data existed). **Numbers:** `RESULT_qwopus.json`, `RESULT_control_CR_vs_CA.json`.
**Raw:** `quant-abstention/raw/main_QWC.jsonl`, `main_C.R.jsonl`.

## Control

The same-day base replay (C.R) reproduces the stored ceiling (`main_C.A.jsonl`, run 2026-09-26) **byte for byte on
all 240 items**: same file, same build, five and a half weeks later. So the comparison below is against a base that did
not drift.

## The result

| | Qwopus Coder Flash Q8_0 | base Qwen3.8-27B Q8_0 | Qwopus - base [95 % CI] | McNemar p |
|---|---:|---:|---:|---:|
| hard real items correct | 0.48 | 0.50 | -0.02 [-0.07, +0.03] | 0.69 (2 vs 4) |
| **invented items refused** | **0.53** | 0.60 | **-0.07** [-0.13, -0.02] | **0.039** (1 vs 8) |
| **invented items answered (made up)** | **0.47** | 0.39 | **+0.08** [+0.02, +0.14] | **0.022** (9 vs 1) |
| easy items correct | 0.825 | 0.85 | -0.025 | 1.0 |
| hard real items refused | 0.01 | 0.03 | -0.02 | 0.63 |
| unfinished | 0 of 240 | 2 of 240 | | |
| mean P(UNKNOWN) at the answer slot, invented items | 0.66 | 0.70 | descriptive | |

- **No knowledge gained or lost** at this resolution: hard accuracy 0.48 vs 0.50.
- **It refuses fewer invented questions and answers more of them.** Where the two disagree on invented items, the base
  refused and Qwopus answered 8 times; the reverse happened once. Its invented answers are fluent and specific: a
  capital for a region that does not exist, and publication years with magazine serialisations for novels that were
  never written.
- **Grades agree on 0.91 of items.** Decode speed is the same (median 9.9 t/s on two P100s).

## Predictions

| # | claim | result |
|---|---|---|
| P1 | code distillation adds no facts (hard QWC - base <= +0.02) | **held:** -0.02 |
| P2 | the fine-tune lowers refusal of invented items by >= 0.05 | **held:** -0.07 (p = 0.039) |
| P3 | the base replay reproduces the stored ceiling (>= 238 of 240 grades) | **held:** 240 of 240, byte-identical |

## What this adds

The fourth fine-tune on this instrument to move the same way. Sage-A1.5 cut refusal of invented items by 0.22 against
its base, Spark-X2.6 by 0.15 against 2.5, OrcaRouter's abliteration by 0.08 (p = 0.09), and now Qwopus Coder Flash by
0.07. None of them gained knowledge. Fine-tuning for a skill (code, science, agents, uncensoring) leaves facts alone and
erodes "I don't know".

## Limits

- **Thinking off.** Qwopus was trained mostly on thinking-on data; this measures its direct answers only. Its card's
  numbers (MMLU-Pro subset, coding agent tasks) are thinking-on.
- **One file (Q8_0), greedy, n = 100 per group.** The effect is modest, and its interval runs from 0.02 to 0.13.
- **Nothing here measures coding,** which is what the model is for.
