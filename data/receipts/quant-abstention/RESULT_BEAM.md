# Result -- Reflection Beam 1.0 501B-A23B (2-bit, minimal reasoning) is the best-calibrated model on the instrument: refuses 98 of 100 invented questions, hard 0.86

**Prereg:** `PREREG_BEAM.md` (`0ec35afd`, before any row), Deviation 1 (`99ecb045`, before any row: placement K=28
`-ts 8,6,6,33`, `--no-op-offload`, smoke gates passed). **Analysis:** `analyze_beam.py` -> `RESULT_beam.json`.
**Raw:** `raw/main_BEAM.jsonl`, 240 rows.

**Run (2026-10-17 00:45-04:15):** AtomicChat `AD-IQ2_XXS` (133.8 GB, 3 shards sha256-verified), .194 4x P100 150 W /
1063 MHz, upstream llama.cpp `f74e2fa6a` (after the Beam merge), routed experts of the last 28 MoE layers (76.4 GB) on
CPU. `reasoning_effort: "minimal"` via `--template-kwargs`; `/props` confirmed the file. ~4-5 tok/s decode, ~50 s per
item. Clean: 240/240 `finish: stop`, one `Exact Answer:` per row from content, reasoning present on every row (median
610 characters, about 150 tokens), lenient grader changes no grade, no prose refusals among wrong answers.

**The condition differs from the other arms** (stated in the prereg): Beam has no thinking-off mode, and `minimal` is
its smallest trained reasoning budget. It writes a short analysis first.

## Results

| arm | condition | easy | hard | hard: abstained | invented: refused |
|---|---|---:|---:|---:|---:|
| **BEAM** AD-IQ2_XXS (133.8 GB) | minimal reasoning | **0.975** | **0.86** | 0.02 | **0.98** |
| SVNV Super VL NVFP4 (76.9 GB) | thinking off | 0.95 | 0.86 | 0.01 | 0.92 |
| FNQ2 Flash-Next Q2 (78.9 GB) | thinking off | 0.90 | 0.79 | 0.01 | 0.71 |
| 27B Q8_0 | thinking off | 0.85 | 0.50 | 0.03 | 0.60 |
| BOLT NVIDIA 2-bit QAT (22 GB) | thinking off | 0.675 | 0.41 | 0.01 | 0.16 |
| BOLTTHINK (same file) | thinking on | 0.675 | 0.43 | 0.08 | 0.52 |

## Registered verdicts

| # | prediction | outcome |
|---|---|---|
| P1 | knows at least as much as Flash-Next Q2 | **holds**: hard +0.07 [-0.01, +0.15] |
| P2 | refuses at least as often as the 27B Q8_0 | **holds**: +0.38 [+0.28, +0.48] |
| P3 | less calibrated than Super VL | **does not hold**: refusal +0.06 [+0.01, +0.12], the other way |
| P4 | <= 2 % unfinished | **holds**: 0 % |

Reported: refusal vs Flash-Next Q2 +0.27 [+0.18, +0.37]; hard vs Super VL +0.00 [-0.05, +0.06].

## Its four misses

- **Two confabulations**, both invented regional capitals: "Ribeira do Sul" (Brazil) -> Imbituba, and "Nord-Keléma"
  (Chad) -> Gounou-Gaya. Each reasoning trace begins "Let's think" and reaches for a real nearby town.
- **Two abstentions on real hard questions:** the first-publication year of a 2025 Dan Brown novel (inside its June 2026
  cutoff), and the founding year of a small Brazilian university.

## Reading

At 2 bits, with experts spread across four 2016 GPUs and system RAM, Beam knows as much as Super VL and Flash-Next on
the hard set and almost never invents an answer. It is the first arm above 0.95 refusal, and it keeps hard-question
timidity at 2 %, so this is not refusing everything. Its card reports AA-Omniscience 10.8 (public split); on this
instrument the calibration it implies holds at 2 bits.

**It does this with very little reasoning.** About 150 tokens per item at the minimal budget. Compare Bolt, which needed
thinking on (median ~840 tokens on its refusals) to reach 0.52.

## Not established

- **Minimal reasoning is not thinking off.** Bolt's +0.36 from thinking shows reasoning can matter a lot on this
  instrument, so Beam versus the thinking-off arms mixes model and condition. Beam versus Bolt-with-thinking (0.98 vs
  0.52) is the closer comparison, and it is not close.
- One quant (AtomicChat imatrix 2-bit); BF16 Beam was not measured. `--no-op-offload` (Deviation 1) only affects how
  prompt batches compute the spilled layers.
- No slot readout (Harmony; `--skip-slot`).
- 240 items; the invented-capital template is where its two misses are.
