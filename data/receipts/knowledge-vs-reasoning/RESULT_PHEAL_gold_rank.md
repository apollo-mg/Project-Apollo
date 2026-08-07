# P-HEAL result — pruning demotes the fact without deleting it

**Date:** 2026-08-07. Forced-decode leg, **both arms**, identical probes, `.73` 2×P100 @ 1063 MHz /
150 W, build `tom_default`, `-c 4096 -ngl 99 -sm layer -np 1 --jinja`, thinking OFF (matching the
runs that produced the transitions). G-1a asserted `expert_gating_func = sigmoid` on both.
274 case-runs, ~2.5 min of compute. Pre-registered in `ERROR_STRUCTURE_AND_HEALING.md` §4.

## Headline — the paired base-vs-pruned comparison

Same items, same prompts, one variable. **Gold's own probability under each arm:**

| | confident errors (n=77) | refusals (n=60) |
|---|---|---|
| gold in top-10 at position 0 — **base** | **97 %** | **95 %** |
| gold in top-10 at position 0 — **pruned** | **66 %** | **40 %** |
| gold in top-100 — base / pruned | 100 % / 95 % | 98 % / 88 % |
| paired gold mean-logprob, pruned lower | **61/61 (100 %)** | **45/46 (98 %)** |
| median delta (pruned − base) | **−1.50 nats/token** | **−2.65 nats/token** |

At the answer slot — the position where the fact actually commits — on the 18 cases admitting an
unambiguous slot in both arms:

```
gold                     base rk  pruned rk   base mlp  pruned mlp
Sandro Botticelli              1         61      -0.00       -2.66
Jacques-Germain Soufflot       1         56      -0.00           -
Mount Kenya                    3         55      -1.67       -6.15
Auguste Rodin                  1         25      -0.00       -4.75
Mount Kilimanjaro              2         19      -0.43       -2.02
Immanuel Kant                  1         14      -0.00       -1.94
Ottawa                        77       >100      -4.69           -
pruned gold WORSE than base in 13/13 comparable; median delta -2.25 nats/token
```

**The base model holds these facts at rank 1 with logprob ≈ −0.00 — effectively certainty.
Pruning moves them to rank 14–61 and −2 to −6 nats.** The degradation is universal (100 % of
paired cases) and attributable to the prune, not to the measurement setup. That control is what
makes the rest of this readable.

## What it means for healing

**The fact is demoted, not deleted.** Under the pruned model gold still sits in the top-100 for
95 % of confident errors and 88 % of refusals, and in the top-10 for 66 % / 40 %. At the answer
slot the median pruned gold is ≈ −2.25 nats/token — roughly a 10 % per-token probability, down
from base's ~100 %.

So a healing pass here would be **restoring rank-ordering in a distribution that still contains the
answer**, not teaching the answer back from nothing. That is h4rm0n1c's re-sharpening case, and it
is the cheap one — it does not require the specific facts to be in the healing corpus.

The honest qualifier: ~2 nats is not a rounding error. Base was at *certainty*; the gap to close is
consistent and large enough that "just needs a light touch" is not supported either. What the data
rules out is the expensive branch — facts driven into the tail and needing to be re-learned.

## Prediction scoring (§8) — both confidences were backwards

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-HEAL1** | 77 confident-error cases, gold's first token in top-10 for ≥50 % | 0.35 | **HELD**, 66 % |
| **P-HEAL2** | same bar on 60 refusals | 0.60 | **FALSIFIED**, 40 % |

I predicted refusal would be the recoverable bucket and confident-error the lost one. It is the
other way round, and the prediction I was least confident in is the one that held.

**Neither number should be read as a knowledge measure, and that was written down first.** A
capability probe run before the harness existed showed position 0 selects a *framing*: on "What is
the capital of Canada?" the pruned top-3 is `'The'` (−0.82), `'O'` (−1.50, Ottawa), `'Toronto'`
(−1.70). Gold outranks the emitted answer and the model still said Toronto. §4 named the
answer-slot measure as the interpretable one in advance.

## The refusal arm's confound, and what survives it

The IKP system message is *"Answer factual questions directly and concisely. **If you don't know,
say 'I don't know'.**"* The refusal string is **instructed by the prompt**; the gold answer is not.
That shows in the data — refusal mean-logprobs are uniformly −0.06 to −0.27 across every sampled
case, which is prompt-priming, not confidence.

**So "the refusal beats gold 46/46 by 3.02 nats" does NOT show the fact is weak, and is withdrawn
as evidence.** It compares an instructed continuation against an uninstructed one.

What survives is the **paired** comparison, because both arms receive the identical prompt and the
priming cancels: pruned gold is worse than base gold in 45/46, median −2.65 nats/token. That is a
clean measurement of what pruning did, and it is the refusal-arm number to quote.

## The funnel, stated once

98 CORRECT→WRONG transitions → 5 hand-verified grader artifacts removed → 93 genuine →
77 sharing no token with the gold (the population under test) → **19** admitting an unambiguous
answer slot → **18** with a slot in both arms → **13** comparable after censoring. The
position-0 statistics use all 77; the answer-slot statistics use 13–18. They are different subsets
and are not interchangeable.

## Limits

- **One prune ratio, one model pair, one replicate per arm.** Verdict transitions carry the known
  temp-0 non-determinism; these are the rep2/rep1 pair only.
- **Censoring is one-sided.** Tokens outside top-100 have no exact logprob, so cases where gold is
  most thoroughly lost drop out of every mean. All reported means therefore **flatter gold**, in
  both arms — the paired deltas are less affected than the absolutes, which is the other reason to
  lead with the pairing.
- **Numeric golds contaminate the rank column.** `1896`→`['189','6']` and `1895`→`['189','5']`
  share a first token, so both score rank 1. Affects 4 of 18 slot cases; mean-logprob is unaffected.
- **Slot location is heuristic** — only 25 % of cases qualified. `"the German physicist **X** (the
  letter X)"` has no well-formed slot at all.
- ~0.03 nats of cross-invocation drift from KV-cache state (12 consecutive in-process reads are
  bit-identical). Negligible against 1.5–2.65 nat effects. Canaries stable in all four runs
  (max drift 0.0082 nats, tolerance 0.5).
- **Says nothing about whether healing recovers accuracy** — only which mechanism it must be.
  That is a training experiment, not a measurement.

## Correction to `ERROR_STRUCTURE_AND_HEALING.md` §3

That receipt found 83 % of confident errors share no token with the gold and called it an upper
bound on "the fact is gone." **The bound was very loose.** Output strings said the answer was
absent; the logits put it in the top-100 for 95 % of those same cases. Token-space absence is not
weight-space absence — that gap is the whole result here.
