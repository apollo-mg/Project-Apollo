# Boundary probes — "can it finish this AT ALL, under any config we can run?"

**2026-08-22, Mark's design.** A separate, deliberately *anecdotal* test class. Not run for
every over-thinking question — run when an item fails to terminate and we want to know where
the wall actually is.

## Why this is a different question

`tier_cal` asks *"is this configuration good for daily use?"* A boundary probe asks
**"is this answerable by this model at all, and what does it cost?"** Those are different, and
conflating them is how `NO-STOP` got over-claimed: we measured a failure at 2.3 % of the
vendor's stated budget and briefly described it as a property of the model.

Knowing the boundary is worth having even when the answer is impractical. *"`CAL-U5` needs 40k
reasoning tokens and `turbo3_tcq` KV to answer"* is a real fact about the model. It is also an
explicit statement that you would not run it that way.

## Escalation ladder — stop at the FIRST rung that terminates

| rung | change | why it might work | cost |
|---|---|---|---|
| 0 | baseline `n_predict` 6,144 | reference | — |
| 1 | `n_predict` → 16,384 | plain under-budgeting | 2.7× tokens |
| 2 | `presence_penalty` 1.0 | **the card's own documented remedy for endless repetition** — never tried | free |
| 3 | effort `medium` | removes the *"consider plausible alternatives"* injection | cheaper |
| 4 | `n_predict` → 65,536, ctx 131,072 | 25 % of the vendor's reasoning budget | ~84 min/item |
| 5 | `turbo3_tcq` KV, ctx 262,144 | full spec — only reachable with a turbo codec | needs a rebuilt buun on `.194` |

**Report the first rung that produces an answer, and the rungs that did not.** A question that
terminates only at rung 5 is a different animal from one that terminates at rung 2, and the
distinction is invisible if you only record pass/fail.

## Rules

- **Anecdotal by design.** n=1 per rung is fine. This produces *notes*, never rates, and nothing
  from it may be differenced against `tier_cal` numbers.
- **Record the full ladder**, including rungs that failed — a boundary is defined by both sides.
- **Every claim carries its rung.** Per `AFM-24`, "did not terminate" is meaningless without the
  envelope, and the envelope is now known to be 262,144 (`CORRECTION_BUDGET_VS_SPEC.md`).
- Rung 2 is first-in-line despite being cheap and late-discovered: `presence_penalty` is the
  vendor's documented lever for exactly this failure and we built a whole verdict class without
  trying it.

## First candidates

`CAL-U5` (Treaty of Kellsworth — two stacked false premises) and the `RD-02` code review, which
produced **24,822 chars of reasoning and zero content**. Both are known to fail at rung 0.
