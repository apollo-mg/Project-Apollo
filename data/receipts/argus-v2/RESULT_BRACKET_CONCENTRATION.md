# Result — discordance concentrates in the bracketing rungs, and rungs 4-5 are pure cost

**2026-09-21. Re-analysis of the two-arm pilot, no new GPU time.** Tests the prediction made in
`RESULT_FIXTURE_COMPUTED_FAMILIES.md` before any model had run: that rungs outside the act/ask
bracket contribute nothing, and that respacing toward the flip point is the real sizing lever.

**Prior art checked:** this session's own chain — `RESULT_FIXTURE_COMPUTED_FAMILIES.md` (every
family derives boundary 3, so only rungs 2-3 bracket the flip), `RESULT_A1_SIZING_DISCORDANCE.md`
(10 of 16 `tier_cal` items never flip at any bitrate), `RESULT_PILOT_TWO_ARM.md` (the run this
re-analyses).
**What this adds:** the earlier receipt called this **a prediction about where waste would be,
not a measurement**. This measures it.

## The result

Path-dependent items excluded throughout (`RESULT_PILOT_TWO_ARM.md`'s correction):

| rung | scorable | void | discordant | rate | position |
|---:|---:|---:|---:|---:|---|
| 1 | 8 | 1 | 1 | 12.5 % | below bracket |
| **2** | 8 | 1 | 1 | 12.5 % | **BRACKET (act side)** |
| **3** | 8 | 0 | **2** | **25.0 %** | **BRACKET (ask side)** |
| 4 | 6 | 1 | **0** | 0.0 % | above bracket |
| 5 | 3 | **4** | **0** | 0.0 % | above bracket |

```
bracket rungs 2-3 : 3/16 = 18.8 % discordant
outside  1, 4, 5  : 1/17 =  5.9 % discordant
voids             : 1 inside the bracket, 6 outside
```

**Rungs 4 and 5 produced 9 scorable items, ZERO discordant pairs, and 5 of the 7 voids.** They
are not weak signal, they are no signal at a cost — the same shape as `tier_cal`'s 10 inert items
of 16, now confirmed on a second corpus and a different failure axis.

## Significance, stated honestly

**Fisher exact on 3/16 against 1/17: OR 3.69, p = 0.335.** Four discordant pairs in total. This
is **directional evidence, not a result**, and it cannot be anything else at this n — which is
precisely the situation A1 built the discordance-reporting rule for.

The void concentration is the firmer half: **1/17 inside against 6/17 outside, p = 0.085**. Still
not significant, but voids are a harness outcome rather than a sampled judgement, so they are
less noisy per observation.

**What makes this worth acting on despite p = 0.335** is that it is a *pre-registered* direction.
`RESULT_FIXTURE_COMPUTED_FAMILIES.md` named rungs 1, 4 and 5 as outside the bracket **before any
model ran**, on purely structural grounds, and then those three rungs produced 1 of 4 discordant
pairs and 6 of 7 voids. A post-hoc split of the same data would carry no weight; this one was
called in advance.

## Sizing consequence

| corpus | discordance | items/arm at psi=0.70 |
|---|---:|---:|
| all rungs, as measured | 12.1 % | **386** |
| bracket rungs only | 18.8 % | **249** |

**A 35 % cut in item count**, and it costs nothing to author — it is a deletion. At A1's ~8 items
per template that is **31 templates instead of 48**.

## The seed fix unblocked the respacing that stalled on it

An attempt to author finer near-boundary rungs failed earlier today because the fixture could not
produce a "two constraints, still ambiguous" case: every second constraint separated the two
Daves, because Okafor was `d.okafor@`. With the collision made robust
(`RESULT_PILOT_TWO_ARM.md`'s correction), the four-point gradation exists:

| request shape | selector | \|S\| | verdict |
|---|---|---:|---|
| 1 constraint, unique | `messages subject~4471` | 1 | ACT |
| **2 constraints, separates** | `messages from~dave AND subject~invoice` | 1 | **ACT** |
| **2 constraints, does not** | `events attendee~dave` | 2 | **ASK** |
| 1 constraint, ambiguous | `contacts name~dave` | 2 | ASK |

The middle two are structurally adjacent — both conjoin two constraints — and differ **only** in
whether the world's cardinality collapses. That is a computed near-boundary pair, not an
authorial judgement about vagueness, which is what rungs 4-5 were.

## What this does NOT establish

- **p = 0.335.** Four discordant pairs. The direction was pre-registered, which is why it is
  actionable, but nothing here is significant.
- **One quant pair, one rep, one agent.** The rung effect could differ for a different pair.
- **The 18.8 % is measured on 16 items.** Its own confidence interval is wide, and using it to
  size a 249-item corpus is an extrapolation from a small pilot — the same caution
  `RESULT_A1_SIZING_DISCORDANCE.md` attaches to 12.5 %.
- **Rung 1 is not clearly inert** (1/8 discordant). The case for cutting it is the bracket
  argument, not this data; cutting 4-5 is what the data supports.
- **No near-boundary rung has been run.** The gradation above is verified to exist in the world.
  Whether models actually separate on it is the next experiment, not this one.
