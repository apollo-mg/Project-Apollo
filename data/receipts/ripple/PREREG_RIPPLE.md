# Pre-registration -- Ripple-65B-Preview on M1: does a 65B dense model trained from scratch know what a 501B MoE knows, and does it say "I don't know"?

**Registered 2026-11-05, before any Ripple row was collected and before the GGUF existed.** Mark approved the download on
11-05. Only procedure has run: the download (sha256 per shard) and the engine builds.

**Prior art checked:** `ledger_precheck.py "Ripple 65B dense from-scratch model abstention knowledge Beam"` -> found:
- INDEX L538: Reflection Beam 1.0 501B-A23B at 2 bits is the best-calibrated model on M1 (refuses 0.98 of invented items
  at minimal reasoning, hard 0.86); Ripple's card claims to match Beam on Terminal-Bench 2.1 (80.52 vs 80.1);
- INDEX L575: Nanbeige4.3-33B, a dense model on its own base, has the least knowledge of any model measured (hard 0.12);
- INDEX L547: Recursive Flint (RecursiveSI, a different company from Ricursive), hard 0.32, refuses 0.45.

**What this adds:** the first dense model above 33B trained from scratch on M1, against a far larger model it claims to
match on agentic coding.

## Model and file

- `ricursiveAI/Ripple-65B-Preview` @ `30cb3b0e`, BF16 instruct (16 shards, 129.57 GB, sha256 per shard checked).
- Converted by us with llama.cpp `67107ac34f` `convert_hf_to_gguf.py` (Ripple support, #31692, plus its kv-shift fix
  #31683) to a BF16 GGUF, then `llama-quantize` (same commit, no imatrix) to **Q6_K**. Q6_K, not Q8_0: Ripple always
  reasons, and Q8_0 (~69 GB) does not fit four P100s; its CPU layers would cut decode to about 2 t/s.
  The Q6_K's sha256 is recorded in the run header and in `stage.log`.

## Instrument

- .194, 4x P100 at 150 W / 1063 MHz; llama.cpp `67107ac34f` `build_sm60` (`build_67107ac_sm60.sh`).
- `-ngl 99 -sm layer -c 10240 -ctk f16 -ctv f16 -np 1 -fit off --cache-ram 0 -lv 4`, `GGML_CUDA_ALLREDUCE=internal`.
- `run_main.py`, M1 (240 items), greedy, the model's own ChatML template, which **has no thinking switch** (as with
  Beam and Flint, the model decides). So: `--max-tokens 8192` (Beam's effort arms used 8192), `--skip-slot` (a forced
  answer slot is off-distribution for a model that reasons first), `--no-think-check`, `--usage --timeout 7200
  --neutral-penalties`.

## Analysis (`ds41-h2h/analyze_ds41.py`, committed and self-tested; generic over arms)

Ripple (arm RIP) against BEAMMED (Beam, medium effort, the scorecard's highest hard accuracy), BEAM (minimal effort),
SVNV (Nemotron 3.5 Super VL) and C.A (Qwen3.8-27B Q8_0), paired by item. These are different models, quants and
reasoning budgets, so the comparisons describe where Ripple sits; they do not isolate a cause.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **A 65B dense model holds fewer facts than a 501B MoE** | H accuracy RIP - BEAMMED (0.89) <= -0.05 | 0.7 |
| P2 | **...but more than the 27B** | H accuracy RIP >= 0.50 (C.A) | 0.75 |
| P3 | **Light, coding-focused post-training does not reach Beam's calibration** | U refused RIP - BEAMMED (0.96) <= -0.10 | 0.6 |
| P4 | **The 8192 budget is enough** | unfinished (TRUNCATED, or INVALID at length) <= 5 % of items | 0.6 |

Reported without a prediction: E accuracy, confabulation, H timidity, reasoning length (`gen_usage`), decode speed.

## Deviations

Any change to the file, flags, budget or analysis after the first RIP row gets a numbered Deviation here.
