# Pre-registration — C3: contradictory context (gold vs the model's own confabulation)

**Logged 2026-08-07, before any C3 inference on either arm.** Probes built and inspected first
(construction is not data); no model has seen them.

## Why this exists

`RESULT_RAG_ARM.md` found full recovery — but **C2 had no teeth**: the base arm also scored 100 %,
so the distractors never demonstrated any power to discriminate. A test that cannot fail on the
control cannot certify the treatment. C3 is the version with a plausible failure mode.

## Design

The reference block holds **two entries for the same question**: one carrying the gold answer, one
carrying the exact wrong answer the pruned model produced closed-book. Nothing in the block
indicates which is right.

```
Reference material:
- What is the capital of Canada?  Ottawa
- What is the capital of Canada?  Toronto

Using only the reference material above, answer:
What is the capital of Canada?
```

**This is not a coin flip, because the arms hold different priors on these same items.** Base
answered them correctly closed-book; pruned produced the confabulation. If the prior leaks into
the choice, base favours gold and pruned favours its own fabrication. Any arm gap is prior leakage
under contradiction — the failure that matters when retrieval returns something the model
"disagrees" with.

**Shape parity is enforced.** A first build put gold `Ottawa` against confabulation `"The capital of
Canada is Toronto"`; the model could then separate the entries by *form* rather than content and
score well for the wrong reason, which would read as robustness. Both entries are now bare answer
spans, reduced by the same conservative rule used in `build_heal_cases.py`. Items where the
confabulation does not reduce cleanly are **dropped, not patched** — 68 of 93 usable.

**Position bias is measured, not assumed.** With only two entries, order could dominate. Every item
is emitted twice — gold-first (**C3a**) and gold-second (**C3b**), n = 68 each, 136 records per arm.

## Predictions (§8)

| id | prediction | confidence |
|---|---|---|
| **P-RAG6** | **GATE** — base gold-rate ≥ 70 %, i.e. priors do measurably influence the choice | 0.65 |
| **P-RAG4** | **HINGE** — pruned gold-rate is ≥ 15 pp **below** base's | 0.45 |
| **P-RAG5** | position bias on the base arm, \|C3a − C3b\|, is ≤ 20 pp | 0.55 |

**P-RAG6 gates P-RAG4.** If base sits near 50 %, the prior does not reach the choice at all, the
design has no signal for either arm, and P-RAG4 is **not scored** — the same gate structure that
P-H2 provided for P-H1, added here because C2 taught us what an ungated ceiling costs.

If P-RAG5 fails, position dominates content; report the two orders separately and treat the pooled
number as uninterpretable.

## Interpretation, fixed before the data

- **Base high, pruned much lower** → the damaged prior overrides supplied context. Retrieval does
  *not* fully rescue the pruned model; it rescues it only when the context is uncontested. This
  would qualify `RESULT_RAG_ARM.md`'s headline materially.
- **Both high** → context grounding beats the prior even under direct contradiction. The RAG
  conclusion strengthens, and C3 becomes the teeth C2 lacked.
- **Both near 50 %** → P-RAG6 fails, nothing is claimed, and the honest report is that a two-entry
  contradiction is decided by something other than either model's knowledge.

## Configuration

Identical to the RAG arm and to every other leg: `ikp_run.py` / `ikp_score.py` unmodified,
`--no-think`, concurrency 1, `--max-tokens 64`, temp 0, K=1, `-c 4096 -ngl 99 -sm layer -np 1
--jinja`, `.73` 2×P100 @ 1063 MHz / 150 W, G-1a `expert_gating_func = sigmoid` asserted from the
load log on both arms. Pruned runs first (currently resident); base follows a swap.

**K=1.** Not reproducible on this fleet — an existence proof, not a rate. With n = 68 per order a
gap under ~10 pp should not be read as real without replication.
