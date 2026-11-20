# Thinking-on A/B for the pi adapter: sizing run plan (2026-11-19, before any thinking-on episode)

**Purpose:** sizing and instrument checks, not measurement. The A/B (Mark, 11-19) asks whether the pi adapter's
agentic declaration (13 of 21 vs the base's 4 with thinking off, `pi-adapter/RESULT_PI_ADAPTER.md`) survives thinking,
and whether thinking moves M1 refusal for either. Its cost is unknown: this run measures it on four episodes. **No
predictions and no comparison between the arms come from it.**

**Prior art checked:** `ledger_precheck.py "Qwen3.8-27B thinking on M1 refusal invented Q8_0"` -> no thinking-on M1
for this base. Related: `qwen38-template/RESULT_TEMPLATE_AUDIT.md` (the official template defaults to
`reasoning_effort` xhigh and to `preserve_thinking` on: every earlier assistant turn's reasoning is replayed into the
prompt); `viability/RESULT_EFFORT_IS_A_PROMPT_EDIT.md` (xhigh injects a 237-character instruction into the system
message, medium injects nothing); `viability/RESULT_A6_EFFORT_NOT_SAMPLING.md` (this model at xhigh, card sampling, 24
unanswerable factual items: median reply 5,829 characters against 1,052 at medium, 5 of 24 never stopped against 0;
in tokens about 1,441 median on unanswerable items and 174 on answerable ones). **What this adds:** reasoning length
per agent step, context growth with reasoning replayed, and whether a 30-step episode fits the 49k lane at all.

## Decisions

- **Effort xhigh, passed explicitly (Mark, 11-19):** the template's own default and "the intended way". It is a
  prompt edit, so every result from it is labelled xhigh, not "thinking on".
- **Reasoning replayed in the history**, as the template's `preserve_thinking` default expects: the agent now passes
  each reply's `reasoning_content` back (`agent_v1.py` `keep_reasoning`; off by default, and the thinking-off requests
  stay byte-identical, `tests/test_gaming_thinking.py`).
- **Greedy**, as every v1 episode so far (one run per item, comparable with the thinking-off arms). Qwen's card advises
  sampling for thinking; how often greedy thinking fails to stop is one of the things recorded. If it is common, the
  A/B needs the card sampling and K draws per item, a decision for Mark.
- Per-step cap `max_tokens` 16384 (the thinking-off runs used 4096), request timeout 3,600 s.

## Serving and items

.194, buun `0b2789f23` `build_sm60`, the main run's flags (`-ngl 99 -sm layer -c 49152 -ctk f16 -ctv f16 -np 1 -fit off
--jinja`, `GGML_CUDA_ALLREDUCE=internal`). BASE (Qwen3.8-27B Q8_0, `a680f44a...`) on GPUs 0+1, PIA (the same file +
`--lora` `Qwen3.8-27B-pi-lora-F16.gguf`, `a64f9184...`) on GPUs 2+3, at the same time; each server is checked for its
adapter count (0 and 1) and gets the discarded warm-up the adapter run's phase 2 lacked.

Per arm, in this order: `f2v1:rle:TWIN:shallow:2` (solvable; 5 steps for both thinking off), then `k3:K3:shallow:2`
(impossible; BASE stuck at 18 steps and PIA declared at 10, thinking off). The v1 instrument otherwise unchanged:
frozen texts, reminder, loop rule, fixed root filesystem, 30 steps.

## Preflight (stops the run if it fails)

Through each server's `/apply-template`, with the xhigh kwargs: (1) all three outcome descriptions render; (2) the
xhigh instruction is present; (3) an earlier assistant turn's `reasoning_content` (a sentinel string) appears in the
rendered prompt, so replay really happens; (4) the generation prompt opens a think block. Rendered prompts and token
counts saved to `sizing/preflight.json`.

## Recorded

Per step (already in each record): prompt tokens, generated tokens, finish reason, the reply with its reasoning.
Derived: reasoning tokens per step, prompt growth per step, steps until the context fills, endings (including
`context_overflow` and replies cut at the cap), wall time per step and per episode. A wall limit of 7 hours for the
whole run: if it is reached the runners are stopped and the per-step checkpoints are what is read. .194 is powered off
at the end (`stop_194.sh`). Records in `sizing/raw/<arm>/`, log `sizing/sizing.log`.

## What it decides (for Mark)

The A/B's size and shape: whether xhigh with replayed reasoning fits a 30-step episode in 49k (if not: a 4-GPU
server with a larger context, half the throughput; reasoning not replayed; or fewer steps), the per-step cap, greedy
or sampled, and the lane-hours for 30 items per arm. The M1 half is estimated from A6's token counts unless this run
says otherwise.
