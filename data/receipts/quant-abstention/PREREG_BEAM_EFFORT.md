# Pre-registration -- what does Beam's reasoning effort buy? Beam 1.0 501B-A23B at effort max / low / high / medium on M1

**Registered 2026-10-17, before any M1 row of these arms.** A sizing probe on items outside M1 ran first (below).

**Why (Mark, 2026-10-17).** More people can now run a model this size locally, on new unified-memory machines and RTX
laptops. For them the question is what Beam's reasoning setting costs and what it buys. Beam's default is `max`; the
registered `BEAM` arm ran at `minimal`, its smallest setting (0.975 / 0.86 / refused 0.98). Cost is reported in
**tokens and characters per answer**, which transfer to other hardware, and in seconds on this fleet, which do not.
A second question is not tested here: whether Beam's speed deficit outweighs its knowledge against Flash-Next or Super
VL for harness work. This receipt supplies the per-answer cost that comparison needs.

**Prior art checked:** `ledger_precheck.py "reasoning effort abstention calibration"` ->
`viability/RESULT_EFFORT_SWEEP.md` (Qwen3.8-27B, 16 items: `low` = `medium` on calibration, `xhigh` converts abstentions
into non-termination at 11.3x the characters; there `reasoning_effort` is an injected system instruction),
`hle-mini/POWER.md` (`low` parsed HLE at 6.3x fewer tokens), `RESULT_BOLT_THINK.md` (thinking on lifted Bolt's refusal
0.16 -> 0.52; refusals deliberate ~4x longer), `RESULT_BEAM.md` (the minimal arm). **What this adds:** a model whose
effort is a trained numeric budget (`Reasoning effort: N` in its Harmony system block), a model already at 0.98 refusal,
the full 240-item M1, and measured tokens and seconds per answer.

## Sizing probe (before this file; not M1; `raw/probe_effort_BEAM.jsonl`, `probe_effort_beam.py`)

Six items outside M1: three P0 hard items (3-8 sitelinks, a band M1 does not use; every P0 easy and invented item is
in M1) and three invented questions written for the probe. Same server as below. Greedy, `max_tokens` 8192.

| effort (budget) | median tokens | median chars | mean s / item | finished |
|---|---:|---:|---:|---:|
| low (32) | 361 | 1,261 | 87.0 | 6/6 |
| medium (64) | 306 | 1,182 | 82.7 | 6/6 |
| high (128) | 398 | 1,561 | 98.5 | 6/6 |
| max (512) | 268 | 1,037 | 73.4 | 6/6 |

The budget does not drive cost on short factual questions at n = 6: every setting lands near 300-400 tokens, against
a median of 690 characters (~190 tokens) for the minimal arm on M1. (The pelican at `max` used ~6,200 tokens: the model
scales its reasoning to the task.) One probe answer changed with effort (medium named a different composer). Probe
grades are orientation only, never a result. About 3.6 characters per token.

## Arms, in this order (each a fresh server)

| arm | `reasoning_effort` | rendered | est. wall time |
|---|---|---|---:|
| **BEAMMAX** | `max` (Beam's default) | `Reasoning effort: 512` | ~5 h |
| **BEAMLOW** | `low` | `Reasoning effort: 32` | ~6 h |
| **BEAMHIGH** | `high` | `Reasoning effort: 128` | ~6.5 h |
| **BEAMMED** | `medium` | `Reasoning effort: 64` | ~5.5 h |

They run unattended in this order from 2026-10-17 evening. If the run is stopped (Mark's call, a fault, or Monday),
arms not completed are reported as not run, and an arm stopped part-way is reported with its n and is not used for a
prediction.

## Instrument (as `PREREG_BEAM`, with these differences)

- **Same model file and placement:** AtomicChat `AD-IQ2_XXS` (133.8 GB, sha256-verified), upstream llama.cpp `f74e2fa6a`,
  .194 4x P100 at 150 W / 1063 MHz, routed experts of the last 28 MoE layers on CPU, `-ts 8,6,6,33`, `--no-op-offload`,
  `-ngl 99 -sm layer -ctk f16 -ctv f16 -np 1 -fit off`, `GGML_CUDA_ALLREDUCE=internal`.
- **`-c 24576`** (BEAM used 4096; KV allocation only, VRAM unchanged within 0.2 GB). Fresh server per arm.
- **Runner:** `run_main.py --template-kwargs '{"reasoning_effort":"<effort>"}' --skip-slot --no-think-check
  --max-tokens 8192 --usage --timeout 3600`. `--usage` (new today, default off) records `gen_usage`, `gen_tps` and
  `gen_elapsed_s` per row. `max_tokens` 8192, not 2048: the probe's longest answer was 849 tokens, and the pelican shows
  the budget can run long. Same corpus, prompt and grader; greedy; `cache_prompt` false.
- **The client runs on .194 itself** (loopback to the server), so the overnight run does not depend on the desktop.
- **Smoke gate per arm:** `/apply-template` must contain the arm's `Reasoning effort: N` line, or the arm does not run.

## Predictions (`analyze_beam_effort.py`, committed with this file, self-tested on stand-in arms; paired bootstrap 10,000, seed 20261020)

Cost is the median total output characters per item (reasoning + content), the one measure the minimal arm has; tokens
and seconds are reported for the new arms.

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **Every setting above minimal costs more per answer** | each arm's median chars >= 1.3x BEAM's (690) | 0.7 |
| P2 | **Above minimal, the setting barely moves cost** | BEAMMAX / BEAMLOW median chars in [0.67, 1.5] | 0.6 |
| P3 | **The default (max) does not lose refusals** | U refusal BEAMMAX - BEAM >= -0.03, CI lower > -0.07 | 0.7 |
| P4 | **The default does not buy knowledge** | \|H acc BEAMMAX - BEAM\| <= 0.05 | 0.55 |
| P5 | **Answers finish** | unfinished (TRUNCATED, or empty-content INVALID with `finish: length`) <= 2 % per arm | 0.85 |

Reported without prediction: every arm against BEAM on E, H, U and timidity with CIs; tokens per item (median, mean,
p90, max) by item group; seconds per item and per arm on this hardware; tokens per correct hard answer; item-level
flips against BEAM; characters per token.

## Stop rules

As `PREREG_BEAM`. A server death resumes the arm on a fresh server (run_main skips written ids), recorded.
