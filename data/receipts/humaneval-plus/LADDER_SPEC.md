# Lab Spec — Puzzle-75B quant ladder: does thinking pay more at lower precision?

**Node:** `.194` quad Tesla P100 (sm_60), 64 GiB VRAM, 60 GiB RAM, 150 W / 1063 MHz.
**Date drafted:** 2026-07-29. **Status:** unblocked — all three quants already on disk.

## The question, and why it is worth running

`offlabel#10` closed 2026-07-29 without merge. Three stacks measured thinking-ON vs -OFF on
single-turn codegen at matched temperature and disagreed:

| stack | model | quant | ON delta |
|---|---|---|---|
| **ours** | Laguna-S-2.1 | **Q2_K_XL** | **+2.84** (paired sign test p = 0.034) |
| @Blackwellboy | Laguna-S-2.1 | NVFP4 | −1.02 |
| @TheTom | Laguna-S-2.1 | Q4_K_M | −2.44 |

The deltas are **monotonic in precision** across three independent stacks. Our own receipt
already states the reading and its limit:

> *"thinking appears to pay at 2-bit and not at 4-bit or above... That is a hypothesis
> consistent with three data points, not a measured mechanism. It needs a single-stack quant
> ladder (same model, same engine, same temperature, Q2 → Q4 → Q6 → Q8) to become a finding.
> **Nobody has run one.**"*

Every participant named this experiment as the decider. It is still unrun.

**Note on Tom's closing summary.** He wrote that "the two [stacks] that held temperature
identical across arms came back flat-to-negative." Ours also held temperature identical
(ON t0.7 vs OFF t0.7, the cell we added specifically to remove that confound) and came back
**+2.84, larger** than the original +2.64. This does not reopen anything — one stack at
p = 0.034 against two contradicting stacks should not hold a PR open, and the closure is
correct. It only means the quant axis, not temperature, is the live explanation.

## Why Puzzle and not Laguna

The disagreement is about Laguna, so a Laguna ladder would be the direct test. **It is blocked
on storage:** `.194` is at 26 GiB free on a 98 %-full volume and only `Laguna-S-2.1-UD-Q2_K_XL`
(37 GiB) exists locally. One Q4 rung would need ~55–60 GiB staged.

Puzzle-75B-A9B has **three quants already on disk**, spanning the precision range where the
effect is claimed to switch sign:

| rung | file | size |
|---|---|---|
| Q2 | `Puzzle-75B-RemySkye/NVIDIA-Nemotron-Labs-3-Puzzle-75B-A9B-Q2_K.gguf` | 29.3 GiB |
| IQ4 | `Puzzle-75B/Puzzle-75B-A9B-UD-IQ4-XL.gguf` | 41.6 GiB |
| Q4 | `Puzzle-75B/Puzzle-75B-A9B-Q4_K_M-0000{1,2}-of-00002.gguf` | 41.7 + 6.3 GiB |

This tests the **mechanism** ("does extra serial compute compensate for quantization damage?")
on a different model, at zero download cost. A null here does not refute the Laguna result,
but a positive would make the quant hypothesis much harder to dismiss as a one-stack artifact.

## Design

**6 cells: 3 quants × {thinking ON, thinking OFF}.**

Held identical across every cell — this is the whole point:
- temperature **0.7**, `top_p 0.95`, `top_k 20`, K=3 (492 samples/cell)
- same engine binary, same `-ngl 99 -sm layer -ts 1,1,1,1 -c 32768 -np 1`
- same harness (`~/hep/hep_eval.py`), same `humanevalplus.jsonl` (164 problems, EvalPlus
  extended suites), same endpoint, same 150 W / 1063 MHz clock state
- **fully GPU-resident** — no `--n-cpu-moe` offload. Puzzle is MoE (9B active) and CPU-expert
  offload would be a fascinating separate test, but it changes arithmetic order and would
  confound a precision comparison.

**Deliberately NOT reusing the existing 93.90 % Puzzle figure.** That run was at temp 1.0 with
creator sampling (`t1.0 / top_p 0.95 / top_k 40 / min_p 0.05`). Mixing it in would reintroduce
exactly the temperature confound that started the whole dispute. Every rung gets a fresh
matched-temperature pair.

**Verification gate, non-negotiable:** `enable_thinking:false` must fire. Confirmed 0/492 for
Laguna across four independent checks; **must be re-verified per quant here** — a template that
silently ignores the flag turns the whole ladder into six copies of one arm.

## Predictions (log before running, score after)

- **P-L1 (0.55):** ON delta decreases monotonically with precision (Q2 > IQ4 ≥ Q4). Low
  confidence — it is the hypothesis under test, and the cross-stack monotonicity could be
  coincidence across three different stacks.
- **P-L2 (0.70):** Q2 ON delta is positive. This is the load-bearing prediction; if the
  mechanism is real it should be strongest where quantization damage is worst.
- **P-L3 (0.65):** the ON arm is less flaky at every rung (Laguna showed 11 vs 30 flaky,
  a 2.7× stability advantage at matched temperature).
- **P-L4 (0.80):** all three quants beat 85 % pass@1 — Puzzle's floor is high, so the ladder
  measures a *delta*, not a capability cliff.

## Cost

~1.5–2 h per cell at K=3 on this node → **9–12 h total**, unattended. Serialised: one server
at a time, 64 GiB VRAM holds exactly one of these at a time.

## Reporting

Whatever the result. A clean null ("thinking is flat across 2→4 bits on Puzzle") is publishable
and directly useful to the offlabel thread — it would suggest the Laguna Q2 result is
model-specific rather than a precision law. The failure mode to avoid is running six cells and
only reporting the ones that agree with our prior.
