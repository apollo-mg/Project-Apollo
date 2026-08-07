# RAG result — the pruning damage is closed-book only

**Date:** 2026-08-07. Both arms, identical probes, `.73` 2×P100 @ 1063 MHz / 150 W, build
`tom_default`, `-c 4096 -ngl 99 -sm layer -np 1 --jinja`, thinking OFF, temp 0, K=1.
G-1a `expert_gating_func = sigmoid` asserted from the load log on both arms (base 29.94 B,
pruned 23.00 B). `ikp_run.py` / `ikp_score.py` unmodified. Pre-registered in `PREREG_RAG_ARM.md`.

## Result

| arm | C1 (clean) | C2 (3 distractors) | CTRL |
|---|---|---|---|
| base | 358/358 — **100 %** | 358/358 — **100 %** | 132/132 — **100 %** |
| pruned | 358/358 — **100 %** | 357/358 — **99.7 %** | 132/132 — **100 %** |

0 errored and **0/848 truncated on both arms** — G-5 clean, no termination divergence.

**The population is the 358 probes the base answered correctly and the pruned arm then lost, so
the pruned arm's closed-book accuracy on it is 0 % by construction.** With the fact in context it
answers every one of them. This is not "the pruned model scores 100 %"; it is **"the pruned model
recovers 100 % of what pruning cost it, once the fact is supplied."**

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-RAG1** | pruned C1 ≥ 90 % | 0.75 | **HELD**, 100 % |
| **P-RAG2** | pruned C2 within 10 pp of base | 0.50 | **HELD**, gap −0.3 pp |
| **P-RAG3** | pruned CTRL ≥ 90 % | 0.80 | **HELD**, 100 % |

## P-RAG2 held, and it should not be leaned on

**The base arm scored 100 % on C2.** The distractors created no measurable interference for the
unpruned model, so the condition has **no demonstrated sensitivity** — a test that cannot fail on
the control cannot certify the treatment. P-RAG2 is satisfied and carries little information.

This was flagged in advance for a different reason (expected ceiling on C1) and is the same defect
the turbo4-K leg hit, where both arms scored 48/48 and the instrument was never shown to
discriminate. Recording it plainly rather than presenting a ceiling as a clean pass.

The one exception is informative. The single pruned failure is precisely the error C2 was built to
detect — **selection from an adjacent distractor**:

```
Reference material:
- Who discovered the law of gravity?  Isaac Newton
- In what year was the Suez Canal officially opened?  1869      <- picked this
- In what year was the Siege of Vienna by the Ottomans...?  1683 <- correct, next line
- What is the capital of Sweden?  Stockholm

pruned answered: 1869
```

Two years, adjacent lines, wrong one chosen. n=1 proves the condition is not *incapable* of
failing; it does not establish a rate, and 1/358 is indistinguishable from noise at K=1.

## What this establishes

**The 25 % prune damaged storage, not use.** Every one of the 358 facts it could no longer produce
closed-book, it produces correctly when handed the fact — including the 98 where it had confidently
fabricated (`Fallingwater` → `"Charles Ahrens."` closed-book, → `Frank Lloyd Wright` with context).
Instruction-following, extraction, and in-context grounding are intact.

This **narrows the campaign's headline, and narrows it in Cerebras's favour**:

> 25 % expert pruning calibrated on code leaves code intact (+1.22 pp HumanEval+), collapses
> closed-book factual recall (−36.8 pp committed accuracy), and **does not impair retrieval-grounded
> answering at all.** These models should not be used as knowledge stores; used with retrieval —
> the agentic setting they are sold for — the measured deficit does not appear.

That is a fairer and more useful claim than the closed-book result alone supports, and it is the
version to publish. The blindness finding survives unchanged: the vendor's panel still cannot see
the closed-book damage, because the panel and the calibration set are the same thing.

It also fits `RESULT_PHEAL_gold_rank.md`. The facts were demoted ~2 nats, not deleted — a context
entry supplies more than 2 nats of evidence, so recovery is what that measurement predicts.

## Limits

- **C2 has no demonstrated sensitivity** (above). A harder condition is required before any claim
  about selection under interference: distractors from the same *domain* rather than the same tier,
  more of them, or a contradictory entry asserting the model's own closed-book wrong answer. That
  last one is the sharpest and is the natural follow-up.
- **K=1, temp 0**, not reproducible on this fleet — an existence proof, not a rate. The 1/358 C2
  failure especially.
- **Reference entries are Q→A pairs**, which is closer to a keyed lookup than to prose retrieval.
  Real RAG hands the model a passage in which the fact is embedded, sometimes implicitly. This
  measures the easy end of the retrieval spectrum.
- Says nothing about **multi-hop** use, conflicting sources, or cases where the retrieved context is
  wrong — all of which are where a damaged model would more plausibly show a deficit.
- One model pair, one prune ratio (25 %), one pruner (Cerebras).
