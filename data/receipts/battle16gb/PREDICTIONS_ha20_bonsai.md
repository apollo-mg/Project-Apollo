# Predictions — Bonsai-27B ternary on HermesAgent-20 (Battle for 16GB, agentic leg)

Logged 2026-07-29 **before any scenario was run**. Scored after.
Gemma-4-12B QAT reference on the same card, same 64k f16 stack: **14/20 PASS, 1 runaway**
(`HA20_SAMPLING_ARMS.md` arm A).

## P-A1 — VRAM feasibility (conf 0.99)

Bonsai serves `-c 65536` at **f16 KV** on a 16 GB card, so this leg carries no KV-codec
confound against the gemma leg.

Derived before launch from GGUF metadata: `full_attention_interval = 4` ⇒ only 16 of 64
layers hold a growing KV; the other 48 are SSM (`ssm.state_size 128`, `ssm.inner_size 6144`)
with constant state. 16 × 4 kv-heads × (256+256) × 2 B = **64 KiB/token → 4.00 GiB at 64k**.

> **CONFIRMED by measurement at launch.** VRAM 2,834,956,288 → 14,986,256,384 B =
> **11.32 GiB** for the server. Weights 7.06 GiB ⇒ **4.25 GiB KV + compute**, against the
> 4.00 GiB prediction.
> A naive all-64-layers reading gives 16.00 GiB — larger than the whole card — and would have
> wrongly forced a quantised-KV arm and a matched gemma control. Recorded because it was my
> first answer.

## P-A2 — Bonsai scores LOWER than Gemma on HA-20 (conf 0.70)

This bets **against** Battle16GB's own result, where Bonsai beat Gemma on both IFEval
(73.0 vs 64.5) and GSM8K-chat (94.0 vs 51.6), decisively.

Mechanism for the reversal, taken from Battle16GB's own mechanism section: Bonsai's
characteristic failure is **over-thinking past the budget** — 20.3 % of IFEval responses were
confirmed 4096-cap deaths. IFEval and GSM8K are single-turn: one over-think costs one answer.
HA-20 is a multi-turn agent loop where every turn is another chance to over-think, and a
scenario needs *all* of its turns to land. A per-turn budget failure compounds across turns
in a way a single-turn suite cannot show.

Gemma's opposite failure (thinking, then EOSing silently — 32 %/46 % empty) is *cheap* in an
agent loop: an empty turn is retried, whereas a turn that never terminates ends the scenario.

## P-A3 — Bonsai produces ≥3 no-verdict runaways (conf 0.65)

Gemma produced exactly 1 (HA-16, 16,492 tokens). Same mechanism as P-A2. Note the timeout is
token-matched, not wall-matched (520 s at 46.02 t/s ≈ gemma's 400 s at 59.34 t/s), so a
runaway cannot be a stopwatch artifact.

## P-A4 — Tool calling survives 1.71 bpw (conf 0.80)

CLAUDE.md's standing warning is that heavily-quantised models go into "2-Bit Drunk" schema
loops under multi-turn JSON tool schemas. At 1.71 bpw Bonsai is the most extreme case this
lab has put under HA-20. Predicted: valid tool calls, failures for task reasons rather than
schema collapse.

> **Pre-confirmed on a single-turn curl smoke** before the batch: `finish_reason=tool_calls`,
> `{"city":"Tokyo"}`, 545 chars of parsed `reasoning_content`. Single-turn only — the
> prediction is about sustained multi-turn schema fidelity, which the batch tests.

## Controls verified before the run

- **Determinism on THIS build** (bonsai fork 10068 + PR #25707, branch `bonsai-rdna4`):
  3/3 byte-identical 1200-token greedy generations, sha `2769dde8ac13d6b4`. K=1 is earned
  here, not inherited from the turboquant-fork receipt.
- **Decode rate**: bonsai 46.02 t/s vs gemma 59.34 t/s (546 real HA-20 turns), 64k f16 KV.
- **Serving config** written to `serving_config_bonsai_ha20.txt` at launch — the original
  Battle16GB per-leg configs were lost to the scratchpad wipe.
