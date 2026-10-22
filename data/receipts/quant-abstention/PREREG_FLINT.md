# Pre-registration -- Recursive Flint (40B total, 2.5B active) on the quant-abstention instrument

**Registered 2026-10-21, before any Flint row on M1.**

**Why.** A new open-weight (Apache 2.0) model released today with receipts on instruction following (IFBench 89.2);
its session-memory result (`session-state/RESULT_SESSION_STATE.md`, Addendum 1) showed format compliance without
extraction fidelity. Mark's standing question: does a model know when it does not know?

**Prior art checked:** `ledger_precheck.py "quant-abstention UNKNOWN abstention"` -> the stored arms on this instrument:
27B Q8_0 `C.A` (hard 0.50, invented refused 0.60), Flash-Next Q2 `FNQ2` (0.79 / 0.71), Super VL `SVNV` (0.86 / 0.92),
Bolt `BOLT` (0.41 / 0.16), Beam `BEAM` (0.86 / 0.98, minimal reasoning). **What this adds:** the smallest active
parameter count on the instrument, and the first same-model thinking-off vs thinking-on pair.

## Condition

Flint's template has no thinking switch; it reasons by default. Two arms, same weights and server placement:
- **FLNT, thinking off:** server `--reasoning-budget 0` (the sampler ends thinking immediately; verified for the
  session-state arm). `max_tokens` 1024 as the stored thinking-off arms.
- **FLTK, thinking on:** server without a budget (default -1), `max_tokens` 8192, `--timeout 3600`.
- **Runner:** `run_main.py --skip-slot --no-think-check --usage` (the template has no `</think>` in its render, and the
  slot readout is not used by these predictions). Same corpus, prompt and grader; greedy; `cache_prompt` false.
- **Model:** Unsloth `flint-Q8_0.gguf` (42,301,076,928 B, sha256 `5df42b56859c7b51...`, verified). **Host and build:**
  .194 4x P100 150 W, upstream llama.cpp `c7fc509` (2026-10-21) sm_60 + gcc-13; `-ngl 99 -sm layer -c 32768 -ctk f16
  -ctv f16 -np 1 -fit off`; client on the desktop over the LAN (:8190).
- **Smoke gates before each arm:** FLNT: a smoke answer has non-empty content and empty reasoning_content. FLTK:
  non-empty content and non-empty reasoning_content.

## Readouts and predictions (`analyze_flint.py`, committed with this file; paired bootstrap 10,000, seed 20261021)

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **2.5B active knows no more than the dense 27B** | H acc FLNT - C.A <= 0 | 0.55 |
| P2 | **Flint (thinking off) refuses invented items clearly less than Super VL** | U refusal FLNT - SVNV <= -0.10, CI upper < 0 | 0.6 |
| P3 | **Thinking makes it refuse more** | U refusal FLTK - FLNT >= +0.05, CI lower > -0.05 | 0.5 |
| P4 | **Answers finish** | unfinished (TRUNCATED, or INVALID with finish length) <= 2 % in both arms | 0.7 |

Reported without prediction: E acc, H timidity, every comparison with BEAM, SVNV, FNQ2, BOLT and C.A for both arms,
FLTK - FLNT hard accuracy, FLTK median reasoning length, decode speed.

## Stop rules

A server death resumes on a fresh server (run_main.py skips written ids), recorded. A failed smoke gate stops that arm.
