# RESULT: Arete-27B keeps its base's knowledge and refuses invented questions less -- the fifth fine-tune to move the same way

**Prereg:** `PREREG_ARETE.md` (`769f8e8a`, Addendum 1 `2a70f266`, both before any row). **Run:** 2026-11-08 15:08-15:58 on .194,
buun `0b2789f23`, ARE on GPUs 0+1 and the base replay C.R2 on GPUs 2+3 at the same time (`run_arete.sh`; log
`quant-abstention/raw/logs/arete.log`). Every gate passed. **Numbers:** `RESULT_arete.json`, `RESULT_control_CR2_vs_CA.json`.
**Raw:** `quant-abstention/raw/main_ARE.jsonl`, `main_C.R2.jsonl`.

**The file:** our Q8_0 from NousResearch/Arete-27B @ `108f0afb` (28,595,764,416 B, sha256 `363c464d...`), converted with
llama.cpp `67107ac34f --outtype q8_0 --no-mtp`. **Tensor-map check** (`tensor_map.txt`): every tensor the two files share
has the same type; the base has 15 more, all `blk.64.*` (its MTP head, unused without speculation; Arete ships none).
**Prompt gate:** the 240 rendered and tokenized M1 prompts hash identically on both servers (`766e6600...`), although
Arete ships a different chat template.

## Control

The same-day base replay (C.R2) is byte-identical to the stored ceiling (`main_C.A.jsonl`) on all 240 items, as C.R was on
11-03.

## The result

| | Arete-27B Q8_0 | base Qwen3.8-27B Q8_0 | Arete - base [95 % CI] | McNemar |
|---|---:|---:|---:|---:|
| easy correct | 0.85 | 0.85 | 0 | 0 vs 0 |
| hard real correct | 0.50 | 0.50 | 0 [-0.05, +0.06] | 4 vs 4 |
| hard real refused | 0.00 | 0.03 | -0.03 | 0 vs 3 |
| **invented refused** | **0.48** | 0.60 | **-0.12** [-0.18, -0.06] | **0 vs 12, p = 0.0005** |
| **invented made up** | **0.52** | 0.39 | **+0.13** [+0.07, +0.20] | 13 vs 0, p = 0.0002 |
| mean P(UNKNOWN) at the answer slot, invented | 0.58 | 0.70 | descriptive | |
| unfinished | 0 | 2 of 240 | | |

- **Knowledge unchanged,** to the item: four hard items flip each way.
- **The change on invented items runs one way only:** on 12 items the base said UNKNOWN and Arete answered; on none did
  Arete refuse where the base answered. The answers are confident: a nonexistent novel dated and attributed to Graham
  Greene, another to E. M. Forster, a capital named for a region that does not exist. The 12 are 5 novels, 5
  universities, 2 regional capitals: none of them touches the political topics Arete was tuned on.
- The forced answer slot moves the same way (0.70 -> 0.58), so the shift is in the model's belief, not only in the
  wording of its answers.

## Predictions

| # | claim | result |
|---|---|---|
| P1 | a values SFT adds no general facts (hard ARE - base <= +0.02) | **held:** 0.00 |
| P2 | it follows the fine-tune pattern (invented refused ARE - base <= -0.05) | **held:** -0.12 (p = 0.0005) |
| P3 | the base replay reproduces the stored ceiling (>= 238 of 240) | **held:** 240 of 240, byte-identical |

## What this adds

Five fine-tunes measured against their bases on M1, five drops in refusal of invented items, no knowledge gained:

| fine-tune | kind | invented refused, change |
|---|---|---:|
| Sage-A1.5 | science / agentic | -0.19 (matched; -0.22 unmatched) |
| Spark-X2.6 (vs 2.5) | version update | -0.15 |
| **Arete-27B** | **values (political and civic topics)** | **-0.12** |
| OrcaRouter abliteration | uncensoring | -0.08 (p = 0.09) |
| Qwopus Coder Flash | code / agent distillation | -0.07 |

Arete was the case most likely to break the pattern: a values tune from a large lab with a strong teacher, on topics
far from M1's. It did not. The skill or value being trained does not seem to matter; supervised fine-tuning without an
abstention signal costs "I don't know" on unrelated questions. The one adapter trained for abstention (Granite's IDK
LoRA) is the only counterexample, and it went the other way. (Counting bare "UNKNOWN" replies, it also refuses 38-69 % of REAL hard facts, which the scorecard's strict
over-refusal metric hid until 11-10: `sci-distill/RESULT_SCI_DISTILL.md`.)

## Independent replication and a caveat (2026-11-08)

- **Replicated on a different stack** (Jorge Leon, HF discussion #23 on NousResearch/Arete-27B): 4-bit MLX quants, his own 30 invented questions plus 6 real controls, greedy, thinking off. Base 11/30 UNKNOWN vs Arete 8/30; flips 5 toward fabrication vs 2 back; controls 6/6 for both; a second, independently made base quant scored identically (11/30). Same direction and signature as M1.
- **The Sage row was in question, and the matched rerun confirms it.** Our Sage-A1.5 comparison (`quant-abstention/RESULT_SAGE.md`) paired Sage at Q8_0 with its base at a plain Q6_K, and on his set Sage held its base's rate (15-17/30 vs 15/30). Rerun with both at mradermacher's static Q6_K, same build, base replayed byte-identically (`quant-abstention/RESULT_SAGE_MATCHED.md`, 2026-11-09): -0.19 [-0.28, -0.11], flips 2 vs 21. The mismatch was worth about 0.03. Why his set disagrees stays open: his questions, quants and stack all differ from ours.

## Limits

- Thinking off, greedy, one file (Q8_0, our conversion), n = 100 per group.
- M1 does not measure what Arete was tuned for; Nous's own evaluation covers that.
