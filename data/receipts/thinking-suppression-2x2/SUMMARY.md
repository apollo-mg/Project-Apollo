# Thinking suppression is an INTERACTION: persona × tools, not either alone

**Date:** 2026-07-26 · **Node:** `.194` quad Tesla P100, **1063 MHz / 150 W** (logged at start)
**Model:** `Laguna-S-2.1-UD-Q2_K_XL.gguf` · poolside build, `-c 32768 -np 1 -ngl 99 -sm layer
-ts 1,1,1,1 -fit off -fa off --reasoning on --reasoning-format deepseek --jinja`
**Design:** 2×2 factorial, 15 HumanEval+ problems (every 10th), **K=1**, temp 0.7 / top_p 0.95 /
top_k 20, thinking left at the template default. Each cell ran in its own subshell so
`HEP_SYSTEM` / `HEP_TOOLS` could not leak between cells.

**Persona:** `"You are a senior software engineer. Write clean, correct, production-quality Python."`
**Tools:** 3 function schemas (`read_file`, `write_file`, `run_command`) passed on every request.

## Why this experiment exists

Public reports (TheTom, BlackwellBoy) observed Laguna thinking almost never firing in agent
pipelines — 3/2944 turns in one, 5–18 % in another — and inferred **two** suppressors: a named
persona, and "coding-shaped tasks." Our own 492-sample HumanEval+ run is maximally
coding-shaped, used the template's default system message and **no tools**, and thinking fired
on essentially every sample.

The variable nobody isolated is **tools**. Every published measurement came from a pipeline
passing tool schemas each turn, so persona and tools were always co-varied. This separates them.

## Result

| cell | system prompt | tools | thinking fired | mean reasoning | **median per-problem ratio vs base** | pass@1 |
|---|---|---|---|---|---|---|
| **base** | default | no | 15/15 (100 %) | 8 418 ch | — | 15/15 |
| **persona** | PERSONA | no | 15/15 (100 %) | 12 704 ch | **1.09×** (no effect) | 13/15 |
| **tools** | default | **YES** | 15/15 (100 %) | 6 377 ch | **0.92×** | 15/15 |
| **both** | PERSONA | **YES** | **13/15 (86.7 %)** | **3 330 ch** | **0.39×** | 13/15 |

**Neither variable alone suppresses. Together they cut reasoning by ~60 %.**

### The interaction is super-additive

If the two effects simply composed, the `both` cell would sit at 1.09 × 0.92 ≈ **1.00×**.
It is observed at **0.39×**. The joint effect is far larger than the product of the parts —
which is exactly why it was invisible to every measurement that varied them together.

### Robustness (this is the part that matters at n=15)

| comparison | sign test | median ratio | drop-largest-gap |
|---|---|---|---|
| base vs persona | 9/15 longer — **coin flip** | 1.09× | 0.96× |
| base vs tools | 11/15 shorter | 0.92× | 0.73× |
| **base vs both** | **14/15 shorter** | **0.39×** | **0.37×** |

The `both` effect is **not outlier-driven**: dropping the single largest contributing problem
makes it *stronger* (0.39× → 0.37×), and it holds on 14 of 15 problems independently. Under
the null, 14/15 in one direction is p ≈ 0.001.

The `persona` row is the cautionary one. Its **ratio of means is 1.51×**, which reads as
"persona increases thinking by 51 %." That is one problem: `HumanEval/30` went 2 260 → 71 375
characters (a 31.6× wedge). Drop it and the ratio is 0.96×. Sign test 9/15. **The persona has
no detectable effect on reasoning length** — the mean was reported first and had to be
retracted, which is the same failure mode that has now bitten this campaign four times.

### Firing rate vs reasoning length are different claims

The public discussion is about thinking *firing*. What we measure cleanly is *length collapse*.
Firing only failed in the `both` cell, 2/15 (the only zero-reasoning samples in the whole
experiment — every other cell has a nonzero floor: base 1 875, persona 835, tools 447). Two
events out of 15 is **not** statistically distinguishable from 0/15 (Fisher p ≈ 0.48).

So the defensible statement is: **persona + tools together collapse reasoning length ~2.5×,
and are the only condition in which thinking failed to fire at all.** A firing-rate claim needs
more samples.

### Accuracy

`base` 15/15 and `tools` 15/15; `persona` 13/15 and `both` 13/15. With n=15 these are
indistinguishable. No accuracy conclusion is supported — the design was powered for the
thinking measurement, not for pass@1.

## What this resolves

It reconciles the contradiction rather than picking a side. Our ~100 %-firing result (no
persona, no tools) and the public ~0 % results (persona **and** tools) are both correct — they
are different cells of a factorial nobody had run. **"Coding-shaped task" is not the
suppressor; our base cell is maximally coding-shaped and thinks the most.**

## Scope limits

- **K=1**, 15 problems, one model, one quant (Q2_K_XL), one template. This sizes an effect;
  it does not establish a rate.
- The persona bundles an identity claim with a **quality demand** ("clean, correct,
  production-quality"). Which half drives the interaction is unseparated — worth a follow-up
  cell splitting them, now that there is a real effect to attribute.
- The 15 problems are every 10th HumanEval+ id, not a random sample.
- Tools were passed but never *called back* — no tool results re-entered the context. A real
  agent loop feeds tool output back, which is a further untested variable.
- Laguna-specific: its template branches on tool presence. Generalization is untested — the
  KAT 2×2 run earlier showed no suppression in any cell.

## Files

| file | what |
|---|---|
| `sup_results_{base,persona,tools,both}.json` | per-problem buckets, finishes, `rc_chars`, tokens |
| `sup_{base,persona,tools,both}.log` | per-cell console output |
| `queue.log` | orchestration log incl. clock readings |
| `cell_pairwise.py` | the paired/sign-test analysis above |
| `hep_eval.py` / `hep_queue_194.sh` | harness and the 2×2 driver as run |
