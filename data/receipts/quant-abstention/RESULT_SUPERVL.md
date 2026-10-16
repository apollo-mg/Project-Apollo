# Result -- Nemotron 3.5 Super VL 120B-A12B (NVFP4, resource-matched to Flash-Next Q2) is the best-calibrated model on this instrument: refuses 92 of 100 invented questions, hard 0.86

**Prereg:** `PREREG_SUPERVL.md` (`75d923b2`), Addendum 1 (`0de22f47`: resource-matched NVFP4 arm SVNV is primary),
Addendum 2 (`490c1841`: SVNV only, SVQ2 deferred), Deviation 1 (`2e41a4d5`: placement), all before any row.
**Analysis:** `analyze_supervl.py --sv SVNV` -> `RESULT_supervl_nv.json`. **Raw:** `raw/main_SVNV.jsonl`, 240 rows.

**Run (2026-10-15 evening):** .194, 4x P100 at 150 W / 1063 MHz, upstream llama.cpp v0.7.0 `620d222`, flags as FNQ2
plus the placement of Deviation 1 (`-ts 17,17,17,38`, routed experts of the last 12 MoE layers and `token_embd` in host
memory: 19.2 GB `CPU_Mapped`, 54.2 GB across the GPUs). `/props` confirmed the NVFP4 file was the one serving.
Decode 9.3 tok/s (smoke). No deviations during the run: 240/240 `finish: stop`, `reasoning` empty on every row, one
`Exact Answer:` line per row, lenient grader changes no grade, no prose refusals among wrong invented-item answers.

## Results

| arm | bytes | easy | hard | invented: refused | hard: abstained | slot P(UNKNOWN), invented |
|---|---:|---:|---:|---:|---:|---:|
| **SVNV**: Super VL NVFP4 (ggml-org) | 76.9 GB | **0.95** | **0.86** | **0.92** | 0.01 | **0.930** |
| FNQ2: Flash-Next UD-Q2_K_XL (stored) | 78.9 GB | 0.90 | 0.79 | 0.71 | 0.01 | 0.769 |
| FNIQ4: Flash-Next UD-IQ4_XS (stored, not registered here) | 93.7 GB | 0.95 | 0.81 | 0.71 | 0.01 | 0.616 |
| BOLT: Bolt 74B 2-bit QAT (stored) | 22.0 GB | 0.675 | 0.41 | 0.16 | 0.01 | 0.344 |
| 27B Q8_0 (stored) | | 0.85 | 0.50 | 0.60 | 0.03 | 0.699 |

## Registered verdicts (SVNV, per Addendum 1)

| # | prediction | outcome |
|---|---|---|
| P1 | knows less than FNQ2 | **does not hold**: hard +0.07 [0.00, +0.15], the other way |
| P2 | confabulates more than FNQ2 | **does not hold**: refusal +0.21 [+0.11, +0.31], the other way |
| P3 | knows more than Bolt | **holds**: +0.45 [+0.35, +0.55] |
| P4 | confabulates less than Bolt | **holds**: +0.76 [+0.67, +0.84] |
| P5 | <= 2 % truncated | **holds**: 0 % |

Reported: vs the 27B Q8_0, hard +0.36 [+0.26, +0.46], refusal +0.32 [+0.22, +0.42]; easy vs FNQ2 +0.05 [0.00, +0.125].

**Item level against FNQ2:** of the 100 invented items, Super VL refuses 25 that Flash-Next answers, and answers 4 that
Flash-Next refuses. Of the 100 hard items, Super VL gets 11 right that Flash-Next misses, and misses 4 it gets.

## What its 8 confabulations look like

Mostly invented operas attributed to real Italian/German composers ("*Il capitano di Zara* was composed by Riccardo
Zandonai"; 4 of the 8), two bare years, an invented Brazilian municipality, and one invented region it read as
Estonia's real Valga County. The obscure-opera template is where it guesses;
on invented places and people it says UNKNOWN.

## Reading

My predictions were wrong in both directions that mattered. With Bolt's 0.16 as the family prior and Artificial
Analysis listing Super VL at 26 (below Qwen3.8-27B's 34), I expected it to trail Flash-Next. Instead, at matched bytes,
it knows at least as much (CI touches 0) and confabulates far less, and its forced slot is the most decisive of any arm
(0.93 on invented items, 0.05 on hard real ones). The family prior was wrong: Bolt's failure belongs to Bolt (or to its
2-bit QAT), not to Nemotron 3.5. And a composite reasoning index does not predict calibration: AA's index runs with
reasoning on and weights agentic and coding tasks; this instrument is thinking-off factual recall with abstention.

## Not established

- **Bits are not matched, bytes are.** NVFP4 is ~4-bit; Flash-Next's 78.9 GB is a 2-bit body plus ~28.8 GB of
  per-layer embeddings. Against Flash-Next at 4 bits (FNIQ4, 93.7 GB, not registered here) Super VL is still ahead on
  refusal (0.92 vs 0.71). The label-matched SVQ2 arm (deferred) would show what Super VL keeps at 2 bits.
- Thinking off only. One instrument (240 items, Wikidata-built); invented-item tells are shared by all arms.
- Different build and placement from FNQ2 (greedy readout; placement did not move grades in FNQ2 vs FNQ2X).
- ggml-org's NVFP4 is most likely NVIDIA's own quantisation (its card lists the NVIDIA NVFP4 checkpoint as a source)
  but the card does not state it per file.
