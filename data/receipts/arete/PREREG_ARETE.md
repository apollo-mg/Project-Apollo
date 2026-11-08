# Pre-registration -- Arete-27B (Nous Research's values fine-tune of Qwen3.8-27B) vs its base on M1: does a values SFT change what the model knows, or whether it says "I don't know"?

**Registered 2026-11-08, before any Arete row and before the GGUF existed.** Mark approved the download on 11-08. Only
procedure has run: the download (sha256 per shard) and a template comparison.

**Prior art checked:** `ledger_precheck.py "Qwopus Qwen3.8-27B fine-tune distillation abstention knowledge"` (11-03) and the
results since. Every skill fine-tune measured on M1 lowered refusal of invented items, and none gained knowledge:
- Sage-A1.5 -0.22 against its base (INDEX L572);
- Spark-X2.6 -0.15 against 2.5;
- OrcaRouter's abliteration of this base -0.08 (p = 0.09, INDEX L308);
- Qwopus Coder Flash -0.07 (p = 0.039, `qwopus/RESULT_QWOPUS_CODER.md`).

The one adapter trained for abstention (Granite's IDK LoRA) raised it to 1.00.

**What this adds:** the first values fine-tune on M1 (about 20K prompts in seven political and civic categories,
teacher Inkling, SFT only), from a large lab, against the exact base with the same-day base replay as control. Nous
reports no meaningful general-capability regression; none of its evaluations measures abstention.

## Files

| arm | file | source |
|---|---|---|
| ARE | Arete-27B **Q8_0, our conversion** (llama.cpp `67107ac34f` `convert_hf_to_gguf.py --outtype q8_0`) | NousResearch/Arete-27B @ `108f0afb`, BF16, 18 shards, sha256 per shard |
| C.R2 | `Qwen3.8-27B-Q8_0.gguf`, sha256 `a680f44a...` (the ceiling file, `main_C.A.jsonl`) | as `qwopus/` |

- **Template:** Arete ships a different chat template from the base GGUF's (system-message merging and the `high` effort
  alias differ). Rendered with thinking off and no system message, all 240 M1 prompts come out identical under both
  (checked with jinja2 before the run). The run enforces it on the live servers: `ds41-h2h/prompt_gate.py` must print
  the same hash on both, and `run_main.py` enforces C.A's render tail and UNKNOWN ids on both arms.
- **Conversion check (recorded, not a gate):** the per-tensor type map of our Q8_0 against the base file. Converter
  differences that change which tensors stay unquantized are reported with the result.

## Instrument (as `qwopus/PREREG_QWOPUS_CODER.md`)

.194, buun `0b2789f23` `build_sm60`; ARE on GPUs 0+1, C.R2 on GPUs 2+3, at the same time; `-ngl 99 -sm layer -c 4096 -ctk
f16 -ctv f16 -np 1 -fit off -lv 4`, `GGML_CUDA_ALLREDUCE=internal`; `run_main.py` M1, thinking off, greedy, 1,024 tokens,
R-slot on, `--usage`.

## Analysis (`ds41-h2h/analyze_ds41.py`)

Primary: ARE vs C.R2 paired by item (E, H, H abstained, U refused strict and lenient, U confabulated, unfinished;
bootstrap 10,000, seed 20261103; exact McNemar). Control: C.R2 vs stored C.A. Descriptive: mean R-slot P_abs on H and U.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **A values SFT adds no general facts** | H accuracy ARE - C.R2 <= +0.02 | 0.7 |
| P2 | **...and follows the fine-tune pattern on invented items** | U refused ARE - C.R2 <= -0.05 | 0.5 |
| P3 | **The base replay reproduces the stored ceiling** | C.R2 grade-identical to C.A on >= 238 of 240 | 0.9 |

P2 sits at 0.5 on purpose: a values tune from a strong teacher is the case most likely to break the pattern.

## Deviations

Any change to a file, flag, lane or the analysis after the first ARE or C.R2 row gets a numbered Deviation here.
