# Pre-registration -- Reflection Beam 1.0 501B-A23B (AtomicChat AD-IQ2_XXS) on the quant-abstention instrument

**Registered 2026-10-16, before any Beam row and before the file finished downloading.**

**Why.** A US open-weight model (Apache 2.0) whose card reports AA-Omniscience (index 10.8, public split, BF16): a lab
publishing the hallucination-penalising metric. Mark's question: is it as trustworthy as that suggests, measured on
our instrument, at a size this fleet can run?

**Prior art checked:** `ledger_precheck.py "quant-abstention UNKNOWN abstention"` -> `RESULT_FLASHNEXT.md` (FNQ2 hard
0.79, invented refused 0.71), `RESULT_SUPERVL.md` (SVNV 0.86 / 0.92), `RESULT_BOLT*.md`, `RESULT_MAIN.md` (27B Q8_0
0.50 / 0.60). **What this adds:** a fourth model family, the largest model on the instrument, and a 2-bit quant of it.

## The condition differs from every earlier arm, and this is stated up front

Beam has **no thinking-off mode.** Its template (`harmony_xml`, channels `analysis` and `final`) always reasons, with an
effort budget `reasoning_effort` in {minimal 8, low 32, medium 64, high 128, xhigh 256, max 512}, default max; Reflection
says minimal (8) is the smallest effort training sampled. This arm runs at **`reasoning_effort: "minimal"`**, the
nearest match to thinking-off. It is not the same condition: Beam may still write a short analysis before answering.
Comparisons with thinking-off arms are reported with that caveat.

## Instrument

- **Runner:** `run_main.py --template-kwargs '{"reasoning_effort":"minimal"}' --skip-slot --no-think-check
  --max-tokens 2048`. The three flags were added today, default off. `--skip-slot`: a forced `Exact Answer:` straight
  after a Harmony generation prompt, with no analysis channel, is off-distribution, so there is no slot readout.
  `max_tokens` 2048 (not 1024) because Beam always writes an analysis. Same corpus, prompt and grader; greedy;
  `cache_prompt` false. (`enable_thinking: false` is still sent and is ignored by Beam's template.)
- **Model:** `AtomicChat/Beam-1.0-501B-A23B-GGUF`, `AD-IQ2_XXS`, 3 shards, 133,789,612,416 B, sha256 per shard verified
  against the HF lfs oids before loading.
- **Host and build:** .194, 4x P100 at 150 W / 1063 MHz, upstream llama.cpp `f74e2fa6a` (master after the Beam merge
  `01fc3aae8`, ggml-org/llama.cpp#30670), sm_60, CUDA 12.4.131 with gcc-13.
- **Server:** `-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off`, `GGML_CUDA_ALLREDUCE=internal`; routed
  experts of the last K MoE layers on CPU via `-ot` with a byte-balancing `-ts`, smallest K that loads (the SVNV / BOLTQ8
  procedure), recorded. No drafter.
- **Smoke gates before any row:** `/apply-template` must contain `Reasoning effort: 8`; a smoke answer must come back
  with non-empty `content` and the analysis in `reasoning_content` (the server's parser separates the channels).

## Readouts and predictions (`analyze_beam.py`, committed with this file; paired bootstrap 10,000, seed 20261019)

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **The biggest model knows the most** | H acc BEAM - FNQ2 >= 0, CI lower > -0.05 | 0.6 |
| P2 | **Beam refuses invented items at least as often as the 27B Q8_0** | U refusal BEAM - 27B >= 0, CI lower > -0.07 | 0.6 |
| P3 | **Beam is less calibrated than Super VL** | U refusal BEAM - SVNV <= -0.10, CI upper < 0 | 0.55 |
| P4 | **Answers finish** | did not finish within 2048 tokens (TRUNCATED or empty-content INVALID with `finish: length`) <= 2 % | 0.8 |

Reported without prediction: E acc, H timidity, all four comparisons (FNQ2, SVNV, BOLT, 27B), median reasoning length,
decode speed.

## Stop rules

As `PREREG_BOLT.md`; additionally the two smoke gates above. A server death resumes on a fresh server, recorded.
