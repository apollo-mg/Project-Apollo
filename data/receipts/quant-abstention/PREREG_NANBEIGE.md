# Pre-registration -- Nanbeige4.3-33B (Kanzhun, dense, own base model) on the quant-abstention instrument

**Registered 2026-10-25, before any Nanbeige row.**

**Why.** Nanbeige4.3-33B (Apache-2.0, released 2026-10-24; dense 33.1B, plain `LlamaForCausalLM`, 52 layers, GQA 56/8,
512K context) is built on Kanzhun's own base model, not a Qwen fine-tune. It is trained as an agentic "teacher" for
distillation, and its card puts it level with or ahead of Qwen3.8-27B on agentic coding and office tasks. Mark: "Nothing
has been able to compete against Qwen 27B for some time." This is the first dense competitor at 27B-class size on M1.

**Prior art checked:** `ledger_precheck.py "Nanbeige"` -> nothing. On M1 the 27B Q8_0 (`C.A`) scores hard 0.50 and refuses
0.60 of invented items. Sage-A1.5 (`RESULT_SAGE.md`, 2026-10-25) showed an agentic fine-tune lineage cutting refusal by
0.22 against its base, with knowledge kept. **What this adds:** a new model family and lineage, dense like the 27B, at
the same quant level, on the same instrument.

## Arms (M1, 240 items; `run_main.py`; `cache_prompt` false; R-slot readout as every arm)

| arm | model | thinking | decoding | max_tokens |
|---|---|---|---|---|
| N33OFF | bartowski `Nanbeige_Nanbeige4.3-33B-Q8_0.gguf` (sha256 `8523452a...`, repo rev `9beb6842`) | off (`enable_thinking: false`) | greedy (instrument default) | 1024 |
| N33THK | the same | on | the card's reasoning settings: `{"temperature": 0.6, "top_p": 0.95}`, per-item seed `(20261025 + crc32(id)) mod 2^31` | 8192 |

No system message. N33OFF is the instrument's default path, directly comparable to `C.A` (27B Q8_0). N33THK uses sampling
because greedy thinking looped on Sage. Q8_0 is the same recipe whoever quantizes, so the packager matters little.

- **Host and build:** .194 4x P100, default clocks, 150 W, upstream llama.cpp `c7fc509` build_sm60 (llama arch has been
  supported for years); `-ngl 99 -sm layer -c 16384 -ctk f16 -ctv f16 -np 1 -fit off`, weights from `/dev/shm`.
- **Smoke gate (also a tokenizer check, as the GGUF is one day old):** "What is 17*19?" must return content containing
  `323`; thinking-off reasoning must be empty. A failure stops the arm.

## Predictions (`analyze_nanbeige.py`, committed with this file; paired bootstrap 10,000, seed 20261025)

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **It recalls more than the 27B** (more total parameters, both dense) | H acc N33OFF - C.A > 0 (point) | 0.55 |
| P2 | **Agentic training costs refusal, as for Sage** | U refusal N33OFF - C.A < 0 (point) | 0.55 |
| P3 | **Thinking answers finish under the card's sampling** | unfinished <= 5 % in N33THK | 0.6 |

Reported without prediction: thinking on vs off (U refusal, H accuracy, timidity), E accuracy, comparisons with Sage,
its base Qwen3.6, ORN and FLNT, decode speed, median reasoning length.

## Stop rules

A server death resumes on a fresh server (run_main.py skips written ids), recorded. A failed smoke gate stops the arm.
