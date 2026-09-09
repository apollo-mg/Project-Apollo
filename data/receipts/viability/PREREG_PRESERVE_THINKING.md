# PREREG: does `preserve_thinking` matter for AGENTIC work?

**Written 2026-09-08, before the OFF arm runs.** Predictions logged with confidence; scored honestly after.

## Setup

| | ON arm | OFF arm |
|---|---|---|
| run | `qwen38_deploy_det02` (already exists) | to run |
| flag | template default (**= preserve ON**, verified) | `--no-reasoning-preserve` |
| model | `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` | same |
| build | 9070 XT, buun `3823c9eb6` | same |
| grader | fixed (`toolcalls.py`) — det02 **re-scored offline** | fixed |

### The flag was verified, not assumed

`/apply-template` on an identical 2-turn conversation carrying reasoning on turn 1:

| setting | prompt chars | turn-1 reasoning in history |
|---|---|---|
| default (no flag) | 487 | **YES** |
| `--reasoning-preserve` | 487 | YES — byte-identical to default |
| `--no-reasoning-preserve` | 400 | **NO** |

**The template default is preserve-ON.** The server's startup hint — *"chat template supports
preserving reasoning, consider enabling it via --reasoning-preserve"* — prints whenever the template
*supports* the feature and is **not** a state indicator. Reading it as one led me to record det02 as
the OFF arm; the probe reversed that. Without this check we would have run a second ON arm and
measured nothing.

### det02 re-scored through the fixed grader

Its recorded verdicts predate the dispatcher fix and are not comparable to anything scored after it.
Traces survive, so verdicts were recomputed with no GPU:

`PASS 44 / FAIL 9 / INFRA 8`  →  **`PASS 50 / FAIL 3 / INFRA 8`**, valid_pass_rate **0.943** (50/53).

Only the 6 known dispatcher tasks moved. **A first pass also converted 8 INFRA→FAIL and was wrong:**
those tasks have `trace.jsonl` of **0 lines** and `timeout after 360s` in their logs — no trajectory
at all. Their worktrees still hold the task *setup* files, so grading an empty trace against them
returns FAIL from some verifiers, scoring an infrastructure failure as a model failure. Infra
classification is now preserved. Same verdict-collapse this campaign keeps rediscovering.

## Hypothesis

Mark: preserve_thinking earns its keep in prose, where carrying prior reasoning maintains continuity,
but agentic work may not need it — *"unless you're failing at it."*

That last clause is the sharp, falsifiable version: prior reasoning should matter most where the agent
must recall **why a previous attempt failed** — error recovery and multi-step recovery — and least on
single-shot mechanical tasks.

## Predictions

- **P1: overall `valid_pass_rate` differs by < 5 points between arms.** 60%.
  Most tasks in this corpus are short and mechanical; there is little prior reasoning worth carrying.
- **P2: any effect concentrates in `t11_error_recovery` + `t12_real_world`, not uniformly.** 55%.
  This is Mark's hypothesis stated as a location claim, and it is the interesting one — a uniform
  effect would falsify the mechanism even if the totals differ.
- **P3: the OFF arm has FEWER INFRA_ERRORs than the ON arm's 8.** 70%.
  Dropping reasoning from history shortens every prompt after turn 1, so prefill shrinks and the
  wall-clock timeout is hit less often. **This is a confound, not a finding** — see below.
- **P4: OFF arm mean prompt tokens per request drop ≥ 15% vs ON.** 65%. The mechanism behind P3.

## The confound that must be reported, not buried

The harness times out on **wall clock**. The OFF arm carries shorter prompts, so it is mechanically
faster and will time out less. **Fewer INFRA errors in the OFF arm is therefore not evidence that
turning preserve_thinking off improves agentic performance.**

Mitigations: report PASS / FAIL / INFRA separately and never collapse them; compute `valid_pass_rate`
over graded tasks only; record prompt-token counts per arm to quantify the asymmetry directly.

If the arms differ mainly in INFRA count and barely in `valid_pass_rate`, the honest conclusion is
*"preserve_thinking costs throughput and buys little accuracy on this corpus"* — a deployment finding,
not a capability one.

## Known limits

- **K=1 per arm.** Existence proof, not a rate.
- The ON arm ran earlier today under different thermal/uptime conditions (AFM-26). The OFF arm gets a
  freshly restarted server, which is the best available control but not a perfect one.
- 61 tasks, of which only ~6 plausibly exercise multi-turn error recovery. **P2 is under-powered by
  construction** — a null result there is weak evidence, and that is stated now rather than after.
