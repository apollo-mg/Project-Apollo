# Result — 25% expert pruning: code untouched, factual recall collapses

**Date:** 2026-08-07. Two arms, one variable, both axes measured on the same files.

## Headline

| axis | instrument | base | pruned | Δ |
|---|---|---|---|---|
| **code** | HumanEval+ pass@1, 164 problems | 82.32 % | **83.54 %** | **+1.22 pp** |
| **knowledge** | IKP T1, accuracy among committed answers | 93.5 % | **56.7 %** | **−36.8 pp** |

The pruned model is **marginally better at code and catastrophically worse at facts.** Same two GGUFs,
same host, same harnesses, one structural difference: 64 → 48 experts.

## Why: they calibrated on code

Cerebras's card for `GLM-4.7-Flash-REAP-23B-A3B` states the calibration set:

> "Code generation samples (evol-codealpaca), Function calling examples (xlam-function-calling),
> Agentic multi-turn trajectories (SWE-smith-trajectories)"

**All code/agentic; none factual.** REAP scores experts by router-gate × activation-norm over that
set, so an expert that never fires on `evol-codealpaca` reads as low-saliency and is removed. Factual
recall does not fire on code.

Their retention claim — *"Retains all core functionalities including code generation, agentic
workflows, repository-scale understanding, and function calling"* — lists **only capabilities they
calibrated on**. It is accurate and it is not a claim about knowledge. This measurement is what the
sentence does not say.

## HumanEval+ detail

```
arm      N     pass@1    PASS  WRONG  TRUNCATED   consistency
base    164    82.32%     135     18         11   fully 135 / never 29 / flaky 0
pruned  164    83.54%     137     24          3   fully 137 / never 27 / flaky 0
```

The pruned arm gets *more* answers outright wrong (24 vs 18) but truncates far less (3 vs 11),
netting +2 passes. Note the direction: on code the pruned model is **more** decisive; on IKP it was
**less** (42 truncations vs 5). It rambles on facts and commits on code — consistent with the
calibration story.

Our pattern reproduces Cerebras's own: they report HumanEval 94.5 → 95.1 and HumanEval+ 89.0 → 89.0,
i.e. pruned ≥ base on code. We measure 82.32 → 83.54.

## Prediction scoring (§8) — honest, including the ones that cost us

| id | outcome |
|---|---|
| **P-R1** T1 knowledge within ±2 pp | **FALSIFIED**, by −56 pp. The premise was wrong, not the margin. |
| **P-R2** T3+T4 drops ≥5 pp | **HELD FOR THE WRONG REASON** — the fall is real but not tail-selective, so the prediction was right by accident. |
| **P-X1** deletion damages the *tail* of the knowledge distribution | **FALSIFIED.** Damage is broad and roughly uniform (+33–48 pp across T1–T4). The mechanism is not "rare experts pruned first" — it is "experts that don't activate on code pruned first." |
| **P-H1** HumanEval+ arms differ ≤3 pp | **NOT SCORED.** Gated out by P-H2 (below). Exploratory value: +1.22 pp. |
| **P-H2** both arms within 5 pp of 89.0 | **FALSIFIED.** base 82.32 (−6.68), pruned 83.54 (−5.46). Logged at 0.55 confidence. |
| **P-H3** truncation spread under IKP's 23.2 pp | **HELD.** 6.7 % vs 1.8 % = 4.9 pp. |

### On P-H1 being unscored, and why the delta still means something

P-H2 was promoted to a gate on P-H1 precisely so a suspicious absolute value would block the
difference test. It fired, so P-H1 is not scored. **That stands; it is not being reinterpreted after
the fact to rescue a result.**

The delta is nevertheless interpretable, for a reason that predates seeing it: our absolute numbers
sit ~6 pp below Cerebras's on **both** arms, which is an offset of the harness and quantization
(Q6_K, P100, our extraction, temp 0, K=1) applying equally to each. **A uniform offset does not bias
a within-pair delta** — that is the entire point of the paired design (§2). Reported as an
exploratory quantity, clearly labelled, not as a confirmed prediction.

The real error was mine in framing: P-H2 conflated two jobs — *is the instrument alive* and *does
their absolute number replicate*. Those needed to be two predictions with different thresholds.
An alive-check at ≥50 % would have passed cleanly; the replication check failed cleanly. Instead one
prediction did both jobs badly.

## What this establishes

**The differential claim, on one model pair with one variable changed.** A knowledge deficit alone
was equally consistent with "the model is just worse." It is not: code is untouched — marginally
better — while factual recall falls 36.8 pp.

It also demonstrates the blindness directly. Every benchmark in the vendor's retention claim is one
the model still passes. **The panel cannot see the damage**, because the panel and the calibration set
are the same thing.

## Limits

- **One model pair, one prune ratio** (25 %), one instrument per axis.
- **Mode coverage is asymmetric.** The knowledge result holds in *both* thinking modes (~7× either
  way). HumanEval+ was run **thinking ON only**. The code arm's mode-invariance is untested.
- **HumanEval+ is K=1** — an existence proof, not a rate (§7). Mitigated but not replaced by
  `flaky = 0` on both arms.
- Absolute HumanEval+ numbers do **not** replicate Cerebras's 89.0 (see P-H2). Only the paired delta
  is claimed.
- The IKP 2×2 is T1 only; T2–T4 have thinking-OFF at K=5 and no thinking-ON cell.
- Says nothing about other pruning methods, other calibration sets, or quantization — Phase 2's
  precision-reduction axis is untouched, so P-X1's *comparison between mechanisms* remains open.

## Environment (§9)

Build `b100-0967f4997`; `.73`, 2 × Tesla P100-PCIE-16GB @ 1063 MHz / 150 W;
`-c 4096 -ngl 99 -sm layer -np 1 --jinja`; temp 0, K=1, `HEP_MAXTOK=16000`, thinking ON;
`hep_eval.py` with `preflight()` green on both arms (numpy 2.3.5 via apt — its absence silently
zeroed an earlier attempt); dataset `humanevalplus.jsonl`, 11,317,638 B, 164 problems,
fingerprint-verified. Arms `GLM-4.7-Flash-Q6_K` (29.94 B) and `GLM-4.7-Flash-REAP-23B-A3B-Q6_K`
(23.00 B), both unsloth, G-1 packaging parity verified, G-1a `sigmoid` asserted on both before every
run.
