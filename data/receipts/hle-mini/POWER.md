# How big does the subset need to be? (and why HLE is worth subsetting at all)

## HLE discriminates better than anything else in Qwen's own table

Spread across the five models Qwen published, as a fraction of the top score:

| benchmark | range | top | range / top |
|---|---|---|---|
| **HLE** | 18.0 | 40.0 | **45.0 %** |
| Terminal Bench 2.1 | 26.5 | 78.2 | 33.9 % |
| IFBench | 17.0 | 79.5 | 21.4 % |
| SWE-bench Pro | 10.5 | 61.7 | 17.0 % |
| GPQA Diamond | 7.8 | 91.3 | 8.5 % |
| LiveCodeBench v6 | 6.4 | 90.3 | 7.1 % |

GPQA Diamond and LiveCodeBench are nearly saturated — five quite different models land
within 8 points of each other, so most of what they report is noise plus ceiling. HLE spreads
the same five over 45 % of the top score. **That is the case for using it**, and it is why a
*subset* of HLE can still be worth more than a full run of a saturated benchmark.

## The design is PAIRED, which is where the power comes from

Every arm sees the identical question set, so comparisons are paired and McNemar applies:
only questions where the two arms *disagree* carry signal. Smallest true difference
detectable at chi2 >= 3.84:

| n | 10 % discordance | 20 % | 30 % | 40 % |
|---|---|---|---|---|
| 50 (`screen_v1`) | 8.8 pp | 12.4 pp | 15.2 pp | 17.5 pp |
| 200 (`subset_v1`) | 4.4 pp | **6.2 pp** | 7.6 pp | 8.8 pp |
| 500 | 2.8 pp | 3.9 pp | 4.8 pp | 5.5 pp |

Counter-intuitively, **more similar arms are easier to separate**, not harder: two adjacent
quants disagree on few questions, so discordance is low and the test is more sensitive to the
few that flip. The unpaired intuition ("similar things need bigger samples") is backwards
here.

**Correction worth recording.** A first pass at this used independent-sample binomial SEs and
concluded `subset_v1` could not resolve a 9.2 pp gap (it gave a 9.5 pp bound). That was the
wrong model for this design. Paired at 20 % discordance the same 200 questions detect
**6.2 pp**. The unpaired figure is only correct if two runs use *different* question sets —
which is exactly what happens if someone regenerates the subset with their own seed.

## Practical sizing

| use | tier | rationale |
|---|---|---|
| "is this model worth testing" | `screen_v1`, n=50 | gates on parse/truncation/token-spend, not accuracy |
| quantisation deltas within a model | `subset_v1`, n=200 | paired, adjacent quants -> low discordance -> good power |
| cross-model comparison at ~5 pp | n=500 | 200 is marginal once discordance rises above ~30 % |
| any absolute number quotable against published HLE scores | full 2500 | nothing smaller is comparable, and this fleet cannot run it |

## Two things to settle before sharing this with anyone

**1. Seed policy — comparability against contamination.** A single canonical id set makes
everyone's numbers comparable and concentrates all the leak risk on those specific items,
which is a poor thing to do to a benchmark whose whole design fights contamination. Rolling
your own seed is safer and costs the paired power above (different question sets -> unpaired
-> the weaker bound). Both are legitimate; the choice should be explicit rather than
accidental. `build_subset.py --seed N` supports either.

**2. Never publish per-question outcomes.** Traces are gitignored for this reason. Aggregates
and per-category rates are safe; a public list of which HLE ids a model got right is a
partial answer key.

## Status

**Nothing here has been run yet.** These are sizing calculations, not results. The runner has
never executed against a live endpoint, so the answer-parsing regex, the normalisation rules
and the judge fallback are all unexercised. A pilot has to happen before any of this is
offered to anyone else — an untested harness shared publicly is a bug report generator.
