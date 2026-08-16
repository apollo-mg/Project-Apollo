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
| ~~quantisation deltas within a model~~ | ~~`subset_v1`, n=200~~ | **WITHDRAWN — see below. Use HumanEval+ instead.** |
| cross-model comparison at ~5 pp | n=500 | 200 is marginal once discordance rises above ~30 % |
| calibration (RMS calibration error) | `screen_v1` or `subset_v1` | the one metric that stays meaningful when accuracy floors |
| any absolute number quotable against published HLE scores | full 2500 | nothing smaller is comparable, and this fleet cannot run it |

## CORRECTION (2026-08-15): the quantisation-delta row was wrong

The withdrawn row reasoned "adjacent quants -> low discordance -> good power". That inverts
the constraint. Low discordance improves *sensitivity per discordant pair*, but McNemar only
sees discordant pairs at all, and below roughly ten of them the chi2 approximation stops
working. At a floored base rate there are not enough.

Expected discordant pairs at n=200, where `overlap` is the share of one arm's correct answers
the other also gets right:

| base accuracy | ov=95 % | ov=90 % | ov=80 % | ov=70 % |
|---|---:|---:|---:|---:|
| 3 % | 0.6 | 1.2 | 2.4 | 3.6 |
| 5 % | 1.0 | 2.0 | 4.0 | 6.0 |
| 8 % | 1.6 | 3.2 | 6.4 | 9.6 |
| 12.5 % | 2.5 | 5.0 | **10.0** | 15.0 |
| 30 % | 6.0 | **12.0** | 24.0 | 36.0 |
| 40 % | 8.0 | **16.0** | 32.0 | 48.0 |

Minimum base accuracy for `b+c >= 10`: **12.5 %** at 80 % overlap, **25 %** at 90 %, **50 %**
at 95 %. Adjacent quants of one model are strongly correlated — 90–95 % overlap is the
realistic band — so quant comparison on this subset needs a model scoring **25–50 % on HLE**.
That is frontier territory and nothing on this fleet approaches it.

**Use the right base rate for the question.** Quantisation deltas need a benchmark where the
model scores well enough to generate disagreement — HumanEval+ (models land 60–90 %, and the
`.194` ladder already runs it) is the correct instrument. HLE is a *ceiling* test: it answers
"how far behind is local" and "is the model calibrated", not "is IQ3 worse than Q4".

Same class of error as the one this document already records: choosing a statistic before
naming what the design can produce (`FAILURE_MODES.md` AFM-2). The first version got the test
right and the sample-size regime wrong.

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

## Pilot outcome (2026-08-15): Qwen3.5-9B fails the gate, and the gate was right

Smoke (5q, 8192 max, no budget): **0 % parse, 100 % truncation**, 8.1 h projected for 200q.
Budget sweep (10q each, 12288 max): parse 20 % at both 1024 and 2048, median tokens pinned at
the cap.

**Everything except the model works.** The reasoning budget applies exactly as documented —
reasoning length scales with it (~1000 tokens at budget 1024, ~1700 at 2048, ~3500 at 4096).
The prompt format, the `Exact Answer:` parser and the confidence regex all work: runs that
terminate produce clean `Exact Answer: I / Confidence: 100%`.

The failure is that the model **does not terminate**. Capping `<think>` does not make it
conclude — it continues reasoning in `content` for 26,000–37,000 characters. Two flavours seen:

- degenerate repetition (`"Maybe **Richard Feynman**?"` x3, `"$E_8$ contains $D_8$?"` x3)
- coherent but unbounded exploration that never reaches an answer

`dry_multiplier=0.8` changed nothing (8103 tokens with and without, identical to 3 chars), so
this is not the classic greedy-repetition trap that a repetition penalty fixes. The model
simply cannot close out these questions.

**This is the gate working.** `screen_v1` was built to answer "is this model worth a full run"
using parse and truncation rather than accuracy, precisely because accuracy floors. It
answered on question one. The hour spent afterwards trying to fix the harness was an override
of a correct verdict — worth recording as its own process failure.

Consistent with external data: Qwen3.5-9B does not appear on Artificial Analysis' HLE board at
all; the lowest entry is 10.6 %. A 9B is not a candidate.

**Next subject: a 27B.** `Qwen3.6-27B` scores 23.1 % there and `Qwen3.8-27B` is a generation
newer, so it is the first model on this fleet with a plausible non-zero score — and at ~23 %
it is also the first that could generate enough discordant pairs for the quant comparison
withdrawn above, at n=500 if not n=200.
