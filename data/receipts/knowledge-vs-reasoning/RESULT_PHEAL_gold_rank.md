# P-HEAL result — the lost facts are still in there, just outranked

**Date:** 2026-08-07. Forced-decode leg on the pruned arm (`GLM-4.7-Flash-REAP-23B-A3B-Q6_K`),
`.73`, 2×P100 @ 1063 MHz / 150 W, build `tom_default`, `-c 4096 -ngl 99 -sm layer -np 1 --jinja`,
thinking OFF (matching the runs that produced the transitions). 137 cases, ~75 s of compute.
Pre-registered in `ERROR_STRUCTURE_AND_HEALING.md` §4 before any of it ran.

## Prediction scoring (§8) — both confidences were backwards

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-HEAL1** | on the 77 confident-error cases, gold's first token in top-10 for ≥50 % | 0.35 | **HELD**, 66 % |
| **P-HEAL2** | same bar on a 60-case sample of the refusals | 0.60 | **FALSIFIED**, 40 % |

I predicted refusal would be the recoverable bucket and confident-error the lost one. It is the
other way round on this measure, and the one I was least confident about is the one that held.

**But P-HEAL1 is not the measure to interpret, and that was written down before the run.** A
capability probe showed position-0 selects a *framing*, not a fact — on "What is the capital of
Canada?" the pruned arm's top-3 is `'The'` (−0.82), `'O'` (−1.50, Ottawa), `'Toronto'` (−1.70).
Gold outranks the answer the model actually emitted, and the model still said Toronto. §4 of the
prereg named the answer-slot measure as the interpretable one for exactly this reason.

## The interpretable measure — gold vs the emitted answer, at the answer slot

19 of 77 cases (25 %) admitted an unambiguous truncation point; 18 produced comparable numbers.
The other 58 are reported, not silently dropped — a heuristic that guesses the slot corrupts the
measurement, so cases without a clean one contribute to measure A only.

```
gold                    emitted             g.rank  e.rank    g.mlp    e.mlp
Mount Kilimanjaro       Mont Blanc              19    >100    -2.02        -     <- gold OUTRANKS
Miguel de Cervantes     Francis Pagnier          4       1    -1.67    -2.09     <- gold OUTRANKS
Immanuel Kant           René Descartes          14       1    -1.94    -0.06
Toulouse, France        Farnborough             17       1    -1.40    -0.36
Auguste Rodin           Pablo                   25       1    -4.75    -0.92
Ottawa                  Toronto               >100      25        -    -5.75
```

**Gold's per-token mean logprob is lower than the emitted answer's in 11 of 12 comparable cases,
median −1.70 nats/token.** So at the position where the fact commits, the model does prefer the
wrong answer — but by a margin of a few nats, not the tens you would see if the fact were erased.

## Refusals — gold vs "I don't know", identical prefix, no slot heuristic needed

This arm needs no truncation point, which is why it is the cleaner half.

```
comparable cases                                  46/60  (14 censored beyond top-100)
gold preferred over the refusal                    0/46
median delta (gold - refusal), per-token mean    -3.02 nats   [min -6.64, max -0.25]
gold within 2 nats/token of the refusal          12/46 (26%)
```

The model prefers refusing, unanimously and by ~3 nats/token (≈ 5 % of the refusal's probability).

## What this says about healing

**The facts are not gone.** Gold's first token is inside the top-100 of a ~151 k vocabulary for
**95 %** of confident-error cases and **88 %** of refusals — the top 0.07 % of the distribution.
At the answer slot, gold is inside the top-20 for 9 of 18. On two cases it outranks the answer the
model actually produced.

**They are outranked, by a few nats.** 1.7 nats/token at the answer slot, 3.0 against a refusal.
That is a 5–20× probability ratio: real, consistent, and far smaller than re-learning a fact from
scratch would imply.

So h4rm0n1c's framing survives the test it could have failed. A healing pass here would be
**re-sharpening a distribution that still contains the answer**, not teaching the answer back.
That is the cheap case — plausibly LoRA-scale, and it does not require the specific facts to be
present in the healing corpus, only enough signal to restore calibration.

The counterpart, which the earlier string-level analysis got wrong: `ERROR_STRUCTURE_AND_HEALING.md`
§3 found 83 % of confident errors share no token with the gold and called it an upper bound on
"the fact is gone." **That bound was loose.** Output strings said the answer was absent; the logits
say it is present at rank ≤100 in 95 % of those same cases. Token-space absence is not weight-space
absence, and here the difference is the whole result.

## Limits

- **One arm, one prune ratio, one replicate.** No base-arm comparison — the interesting contrast
  (is gold's rank *lower* in pruned than in base?) is one more run and is not measured here.
- **Numeric golds contaminate the rank measure.** `1896`→`['189','6']` and `1895`→`['189','5']`
  share their first token, so both score `first_rank=1` — that is the shared prefix, not the fact.
  Affects the rank column on 4 of 18 slot cases; the mean-logprob comparison is unaffected.
- **Censoring is one-sided.** Tokens outside top-100 have no exact logprob, so cases where gold is
  most thoroughly lost drop out of the mean-logprob statistics (14/60 refusals, 6/18 slot cases).
  Every reported mean therefore **flatters** gold. The direction of that bias is toward the
  conclusion, and it is the main reason not to lean harder on it.
- **Slot location is heuristic**, which is why only 25 % of cases qualified. Cases like
  `"the German physicist **X** (the letter X)"` have no well-formed slot at all.
- ~0.03 nats of run-to-run drift from KV-cache state (12 consecutive in-process reads are
  bit-identical; the drift appears across invocations). Negligible against 1.7–3.0 nat effects.
  Canary `('Paris', −0.064)` stable start-to-end, drift 0.0082 nats.
- Says nothing about whether healing actually recovers accuracy — only which mechanism it needs
  to be. That is a training experiment, not a measurement.
