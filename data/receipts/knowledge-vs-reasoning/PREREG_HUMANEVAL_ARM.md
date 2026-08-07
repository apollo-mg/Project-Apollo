# Pre-registration — HumanEval+ reasoning arm (Phase 1 completion)

**Logged 2026-08-06, before any HumanEval+ inference on either arm.** Commit timestamp is the record.

## Why this run decides the campaign

The knowledge half is measured: 25% expert pruning multiplies confident factual error ~7×
(`PHASE1_RESULT_COMMITTED_ERROR.md`). That alone is **equally consistent with the model simply being
worse at everything.** The thesis — knowledge degrades *faster than* reasoning — is a **differential**
claim and is untested until a reasoning benchmark runs on the same two arms.

## The calibration finding that reframes this (discovered before the run)

Cerebras's own card for `GLM-4.7-Flash-REAP-23B-A3B` states the calibration set:

> "Code generation samples (evol-codealpaca), Function calling examples (xlam-function-calling),
> Agentic multi-turn trajectories (SWE-smith-trajectories)"

**All three are code/agentic. None are factual.** REAP scores experts by router-gate × activation-norm
over that set, so experts that do not fire on code read as low-saliency and are removed. Factual-recall
experts do not fire on `evol-codealpaca`.

This is a **better mechanism than the one pre-registered as P-X1**, and it retro-explains the observed
tier profile that falsified P-X1: damage was broad and uniform (+33–48 pp across T1–T4) rather than
tail-selective, because the selection criterion is not *rare* — it is *does not activate on code*.

Their reported numbers, which this run replicates:

| | base | REAP |
|---|---|---|
| HumanEval | 94.5 | 95.1 |
| HumanEval+ | **89.0** | **89.0** |

And their retention claim: *"Retains all core functionalities including code generation, agentic
workflows, repository-scale understanding, and function calling"* — **every listed capability is one
they calibrated on.**

## Predictions (§8)

| id | prediction | confidence |
|---|---|---|
| **P-H1** | HumanEval+ pass@1 differs between arms by **≤3 pp** (their claim: 0.0 pp) | 0.80 |
| **P-H2** | Both arms land within 5 pp of Cerebras's 89.0, i.e. the number replicates on our harness | 0.55 |
| **P-H3** | HumanEval+ `no_answer`/truncation spread between arms stays **under** the IKP thinking-ON spread of 23.2 pp | 0.70 |

### AMENDMENT (2026-08-06, before any *valid* HumanEval+ inference)

**P-H2 is promoted from a side prediction to a GATE on P-H1.** If either arm falls outside 5 pp of
89.0, P-H1 is **not scored at all** — neither held nor falsified.

The first attempt at this leg produced 0% on every problem because `PREAMBLE` imports numpy and `.73`
had none, so the import raised before any test executed (`hep_eval.py` now aborts on this via
`preflight()`; see commit `20712d7`). That run is **not data** — the grader could not pass the
dataset's own canonical solution — so this amendment is made with zero valid observations in hand.

The reason for the change is a design flaw in P-H1, visible now that the failure mode has been seen:
**a dead harness satisfies it perfectly.** 0% vs 0% is a 0.0 pp difference and would have scored P-H1
as HELD, confirming the campaign's hinge prediction from two zeros. Unlike the knowledge result —
where `raw` and `answered` disagreeing forced a second look — P-H1 has no internal contradiction to
trip on.

A prediction a broken instrument can satisfy is a weak prediction. P-H2 supplies the absolute-value
sanity check that distinguishes *"the arms match"* from *"the harness is dead"*, and P-H1 is
uninterpretable without it.

**P-H1 is the campaign's hinge.** Combined with the measured ~7× knowledge damage:

- **P-H1 holds** → code preserved, facts destroyed, on one model pair with one variable changed. The
  differential claim is established and the mechanism is named.
- **P-H1 fails** (large HumanEval+ drop too) → the prune damaged the model broadly, the "knowledge is
  special" framing dies, and the honest result is "25% expert pruning is not near-lossless, including
  on the axis its authors calibrated for."

Both outcomes are worth publishing. Only one supports the thesis.

P-H2 is deliberately low-confidence: our harness, quant (Q6_K), hardware and sampling differ from
theirs, so an absolute mismatch would not by itself impeach their number.

## Configuration, fixed in advance

Identical on both arms; any deviation invalidates the pair.

| field | value |
|---|---|
| harness | `hep_eval.py` (`data/receipts/humaneval-plus/`), `WORKERS=1` — single in-flight, no batch-nondeterminism |
| dataset | `humanevalplus.jsonl`, 11,317,638 B, 164 problems — fingerprint-verified against `fetch_dataset.py` |
| `HEP_TEMP` | 0 |
| `HEP_K` | 1 |
| `HEP_MAXTOK` | 16000 — deliberately generous; the IKP run showed a tight cap manufactures a false deficit |
| `HEP_THINK` | **1 (thinking ON)** — the deployment mode for code and the mode their 89.0 presumably used |
| server | `-c 4096 -ngl 99 -sm layer -np 1 --jinja`, build `b100-0967f4997`, `.73` 2×P100 @ 1063 MHz / 150 W |

**Mode caveat, stated up front.** IKP showed thinking-mode is *not* neutral between these two arms
(§6). This run fixes thinking ON for both. If P-H1 holds under ON it is suggestive but not complete;
the OFF cell is required before claiming mode-invariance the way the knowledge result can, where ~7×
held in both modes.

## Scoring

Report pass@1 with the same three-bucket discipline as IKP: PASS / WRONG / TRUNCATED, with
truncation reported separately per arm and never folded into failures. G-5's 2 pp rule applies — a
divergent truncation rate voids the comparison exactly as it did for IKP thinking-ON.
