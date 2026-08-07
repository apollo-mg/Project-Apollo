# C3 result — under contradiction the pruned model answers by POSITION, the base model by CONTENT

**Date:** 2026-08-07. Both arms, identical probes, `.73` 2×P100 @ 1063 MHz / 150 W, build
`tom_default`, thinking OFF, temp 0, K=1, G-1a `sigmoid` asserted on both. `ikp_run.py` /
`ikp_score.py` unmodified. 136 records per arm, 0 errored, **0/136 truncated on both arms**
(G-5 clean). Pre-registered in `PREREG_C3_CONTRADICTION.md`.

## Result

Reference block holds two entries for one question — gold and the pruned model's own closed-book
confabulation, as bare shape-matched spans — with nothing indicating which is right.

| arm | order | gold | confab | refusal | **gold rate (committed)** |
|---|---|---|---|---|---|
| base | gold 1st | 57 | 0 | 11 | **100.0 %** |
| base | gold 2nd | 57 | 4 | 7 | **93.4 %** |
| pruned | gold 1st | 53 | 4 | 11 | **93.0 %** |
| pruned | gold 2nd | 20 | **39** | 9 | **33.9 %** |

```
ORDER SENSITIVITY  |gold-1st − gold-2nd|      base  6.6 pp      pruned  59.1 pp
arm gap, gold FIRST                           +7.0 pp
arm gap, gold SECOND                         +59.5 pp
```

**The base model picks gold regardless of where it sits. The pruned model largely picks whatever
comes first.** That is the finding, and it is not the one that was predicted.

## Prediction scoring (§8)

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-RAG6** | GATE — base gold-rate ≥ 70 % | 0.65 | **HELD**, 83.8 % pooled |
| **P-RAG5** | base position bias ≤ 20 pp | 0.55 | **HELD**, 0.0 pp raw / 6.6 pp committed |
| **P-RAG4** | pruned ≥ 15 pp below base | 0.45 | **HELD** on pooled, +30.1 pp |

**P-RAG4's pooled number should not be quoted alone.** 30.1 pp is the average of two regimes that
differ by an order of magnitude — +7.0 pp when gold leads, +59.5 pp when it trails. My own
pre-registration said a large position bias makes the pooled figure uninterpretable; it scoped that
rule to the base arm, but it applies with far more force to the pruned arm, which is where the bias
actually appeared. **Report the two orders; the pooled value is an artifact of a 50/50 design
choice.**

The prediction was right for the wrong reason. I predicted *prior leakage* — that pruned would
favour its own fabrication because it still believes it. What the data shows is **positional
fallback**: when gold leads, pruned picks gold 93 % of the time, i.e. it does *not* prefer its own
answer on content. It prefers whichever entry it read first, and only looks like prior-preference
because in half the trials the first entry happens to be its fabrication.

## What this qualifies

`RESULT_RAG_ARM.md` concluded that retrieval fully rescues the pruned model — 358/358 recovered.
That result stands for the condition it measured, and **C3 bounds it**:

> Retrieval rescues the pruned model **when the retrieved context is uncontested.** When retrieval
> surfaces conflicting entries, the pruned model no longer adjudicates on content — it falls back
> on position, and lands on the wrong answer 66 % of the time when the wrong entry is listed first.
> The base model is essentially unaffected by ordering (6.6 pp).

That matters practically, because real retrieval returns conflicting chunks routinely — stale
documents, near-duplicate pages, contradictory sources. A pipeline that assumes the model will sort
truth from a mixed result set is relying on a capability this prune measurably damaged.

It also gives C2 the teeth it lacked. C2 could not fail on either arm; C3 separates them by 59.5 pp
in one order while both arms stay clean on refusals and truncation.

## The refusal behaviour is worth noting separately

Refusals ran 7–11 per cell in **both** arms and both orders — the model saying `"I don't know"` when
handed two contradictory entries. That is the correct response to the prompt as posed, it is
**not** the differentiator, and it is roughly arm-invariant. The pruned model's failure is not that
it refuses more; it is that when it does commit, it commits to whatever it saw first.

## Limits

- **K=1, temp 0**, not reproducible on this fleet — an existence proof, not a rate. n = 68 per
  order. The 59.1 pp order effect is far too large to be sampling noise; the 7.0 pp gold-first gap
  is not, and should not be read as real without replication.
- **Two entries only.** Real retrieval returns more, and primacy effects may behave differently at
  k = 5 or 10. Untested.
- **The contradiction is bare** — two answers, no provenance, no dates, no source quality signal.
  A real pipeline usually supplies something to adjudicate on. This measures the model's behaviour
  when it has *only* content and position to go on, which is the worst case rather than the typical
  one.
- **68 of 93 items usable**; the 25 dropped are those whose confabulation would not reduce to a
  clean bare span, which skews the set toward short, entity-like answers.
- **Position was tested, not source-attribution.** Whether the pruned model can use a provenance
  cue (`[2024 encyclopedia]` vs `[user forum]`) to override position is the obvious next question
  and is not answered here.
- One model pair, one prune ratio (25 %), one pruner.
