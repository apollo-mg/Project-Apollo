# Result -- P-A0 gate: temp 0 is byte-stable, and Bonsai 2 does not fall flat

**2026-09-19, 15:20 to 16:37 on `.73`.** Prereg `PREREG_AGENTIC_LADDER.md` + Amendments 1-2, all
committed before any scenario ran.

Arm **T-BPQ2** = `Ternary-Bonsai-2-27B-PQ2_0.gguf`, 2.119 scored bpw, mean KLD 0.358047 --
deliberately the **most damaged** model in the panel, so that if greedy decoding was going to
break anything it would break here.

## P-A0: CONFIRMED

| | |
|---|---|
| scenarios scored in both passes | **15 / 15** |
| **verdicts identical** | **15 / 15** |
| **tool-call counts identical** | **15 / 15** |
| wall clock | 39 min / 37 min |

Not merely the same outcomes -- **the same execution paths**, several matching to the second
(196/196 s, 168/168 s, 144/144 s, 133/133 s). Temp 0 at `-np 1` is effectively deterministic on
this stack, confirming `agent-benchmark-determinism` for an agentic workload rather than a
single-turn one.

**Consequence for the panel: the noise floor is zero.** The original prereg demanded a >= 3
scenario (~20 pp) margin before calling any difference real, because the prior temp-0.6
calibration flipped 5 of 16 scenarios between passes. That margin is now unnecessary: **a single
scenario differing between two arms is a real difference.** The panel needs **one pass per arm**,
not three to five -- roughly a 4x cost reduction.

## The runaway hazard: retired with evidence

Mark's concern was that greedy decoding cannot sample out of a degenerate state, and that
heavily quantised models are brittle under multi-turn JSON tool schemas ("2-Bit Drunk" loops).

**Observed: 0 RUNAWAY in 30 scenario-runs.** Stopping rule was >4 of 15. One scenario flagged for
review on the time signal alone (`move-sync-implicit`, 495 s vs a 118 s median), reproducing to
within 1 second across passes -- so even the outlier is deterministic.

The model does generate long: `move-sync-implicit` produced **3,768 tokens in a single turn**
against a 143-186 token norm. But it always resolved and acted. **Long deliberation, not a loop.**

## Verdicts, identical in both passes

| verdict | n | |
|---|---:|---|
| CORRECT | **7** | success |
| CLARIFIED | **2** | success (correct to decline on an ambiguous scenario) |
| WRONG | 4 | decision failure |
| NO-ATTEMPT | 1 | decision failure |
| SUSPECT | 1 | decision failure |
| INFRA / TOOL-FAIL | **0** | void |

**9 of 15 successful (60%).** **Zero void** -- the environment never broke, so every failure is a
genuine decision failure. That satisfies P-A3's requirement in advance: the failures are in the
decision classes, not the environment classes.

## What a 2.119 bpw ternary model actually did

`dave-friday-reply` is the scenario built to separate models that read from models that
pattern-match: two Daves have mail, and only one is coherent with "Friday works". B-PQ2 scored
**CORRECT** with 8 distinct tool calls:

```
gmail search "Dave" --max 10   ->  gmail get m3   (the WRONG Dave)
gmail search "is:unread" --max 20
gmail search "meeting OR schedule OR Friday OR call" --max 20
gmail get m2   (the RIGHT Dave)  ->  contacts list  ->  reply
```

It found the wrong Dave, recognised it, widened the search, found the right one, verified against
contacts, and replied. **At 2.119 bits per weight.**

The failures are equally diagnostic:
- `rent-amount` **SUSPECT** with **zero tool calls** -- asserted it had no information about a
  figure that was sitting in the corpus, without looking. Confabulating an absence.
- `move-sync-implicit` **WRONG** after 495 s and 3,768 tokens -- overreach, took two actions.
- `cancel-thursday` **NO-ATTEMPT** in 46 s -- reached for the wrong tool entirely.

## The limit, stated plainly

**60% is uninterpretable on its own.** One arm cannot say whether that is good. The comparison
arms (GSQ-RCO 2.476 bpw, AD 3.732 bpw) and, on the evidence below, a **high-fidelity Qwen3.8
anchor** are what make it a measurement rather than a number.

PrismML's own paper reports **Terminal-Bench 2.1 69.7 -> 52.8** and **SWE-bench Verified
80.6 -> 60.8** for Bonsai 2 against the Qwen3.8 base -- about **76% relative retention**, and
those rows are absent from the GGUF model card's benchmark table. Measuring retention on this
corpus requires the base model as an arm. Without it we can rank codecs against each other but
cannot say what any of them retain.

## Cost, now measured

~38 min per 15-scenario pass, ~150 s per scenario. With determinism giving one pass per arm, a
4-arm panel (three codecs plus a fidelity anchor) is **~2.5 hours** of single-node occupancy.
That is a `.194` job: `.73` hosts the daily driver and Mark's production Hermes gateway.

Raw: `logs/gate_T-BPQ2_p1.jsonl`, `logs/gate_T-BPQ2_p2.jsonl`. Seed `806c5016...`, frozen.
