# Pre-registration -- Qwopus3.8-27B-Coder-Flash vs its base Qwen3.8-27B on M1: does a distillation fine-tune change what it knows, or whether it says "I don't know"?

**Registered 2026-11-03, before any Qwopus row was collected.** Mark approved the download on 11-03. Only procedure has
run: the file's hash and the base file's hash, and a template comparison. No M1 item has been sent to either model.

**Prior art checked:** `ledger_precheck.py "Qwopus Qwen3.8-27B fine-tune distillation abstention knowledge"` -> found:
- INDEX L572: Sage-A1.5, a fine-tune of Qwen3.6-35B-A3B: hard 0.62 against its base's 0.67, and refusal of invented
  items 0.45 against the base's 0.67 (the fine-tune lineage cut it by 0.22);
- INDEX L308: OrcaRouter's abliteration of this same base, Q6_K: factual recall -3.5 pp, invented-entity abstention
  0.55 vs 0.63 (p = 0.09);
- Spark-X2.6 vs 2.5: honesty down on every primary measure, knowledge unchanged;
- INDEX L55: an earlier Qwopus3.8-Flash GGUF from another packager never opened `<think>` (template copied from the
  safetensors repo); Jackrong's own GGUF shipped the stock template.

**What this adds:** a distillation fine-tune (about 200K code, agent and reasoning examples from Qwen3.8-Flash-Max,
Qwen3.8-Max, DeepSeek-V4-Flash and Nemotron data) against its exact base, with a same-day base replay as the control.

## Files

| arm | file | source | sha256 |
|---|---|---|---|
| QWC | `Qwopus3.8-27B-Coder-Flash-Q8_0.gguf`, 29,047,085,312 B | Jackrong/Qwopus3.8-27B-Coder-Flash-GGUF @ `603caf4c` | `d1262b7b...` (published, checked after download) |
| C.R | `Qwen3.8-27B-Q8_0.gguf`, 29,047,086,048 B | the main campaign's ceiling file | `a680f44a...` (= `main_C.A.jsonl`'s) |

- **Templates:** the Qwopus GGUF's chat template is byte-identical to the base file's (9,993 chars; read from
  Hugging Face's GGUF metadata, and re-checked on the downloaded Q8_0 before the run). So the prompts are identical,
  and the runner enforces C.A's render tail and UNKNOWN ids on both arms.

## Instrument (as `quant-abstention/PREREG_MAIN.md`'s ceiling arm)

- .194, buun `0b2789f23` `build_sm60`; two lanes, **QWC on GPUs 0+1** and **C.R on GPUs 2+3**, at the same time,
  each `-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off -lv 4`, `GGML_CUDA_ALLREDUCE=internal`. The main
  campaign's bridge check showed the two lanes byte-identical (C.A vs C.B: 240 of 240).
- `run_main.py`, M1 (240 items), thinking off, greedy, `max_tokens` 1024, R-slot on (the UNKNOWN variants are single
  tokens here), `--usage`. Fresh servers; the runner's own warm-up is discarded.

## Analysis (`ds41-h2h/analyze_ds41.py`, already committed and self-tested; it is generic over arms)

- **Primary:** QWC vs C.R paired by item: E and H accuracy, H abstained, U refused (strict and lenient), U confabulated,
  unfinished; difference, 95 % bootstrap CI (10,000, seed 20261103), exact McNemar.
- **Control:** C.R vs the stored C.A: grade and `content` identity.
- If C.R does not reproduce C.A, C.R stays the comparison (same day, same build) and the drift is reported.
- Descriptive: mean R-slot P_abs on H and U per arm.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **Code distillation adds no facts** | H accuracy QWC - C.R <= +0.02 | 0.7 |
| P2 | **The fine-tune lowers refusal of invented items** (Sage, Spark, OrcaRouter precedent) | U refused QWC - C.R <= -0.05 | 0.6 |
| P3 | **The same-day base replay reproduces the stored ceiling** | C.R grade-identical to C.A on >= 238 of 240 | 0.85 |

Reported without a prediction: E accuracy, confabulation, unfinished, P_abs, speed. Limit stated in advance: thinking
is off, and Qwopus was trained mostly on thinking-on data, so this measures its direct answers only.

## Deviations

Any change to a flag, file, lane or the analysis after the first QWC or C.R row gets a numbered Deviation here.
