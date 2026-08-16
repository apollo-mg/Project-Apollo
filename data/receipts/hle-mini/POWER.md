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

## Round 2 (2026-08-16): sampling is NOT the cause — a clean null, and two falsified predictions

| run | model | sampling | parse | truncation | median wall |
|---|---|---|---|---:|---:|
| 1 | Qwen3.5-9B `Q8_0` | deterministic | 20.0 % | 80.0 % | 218 s |
| 2 | Qwen3.8-27B `Q6_K` | deterministic | 20.0 % | 80.0 % | 612 s |
| 3 | Qwen3.8-27B `Q6_K` | **recommended** | 20.0 % | 80.0 % | 716 s |

Three runs, two models differing 3x in parameters and one quant tier apart, two sampling
regimes as opposite as they come (`temp 0 / top_k 1` against `temp 1.0 / top_p 0.95 /
top_k 20`). **Identical 20 % parse, identical 80 % truncation.** And the same questions closed
and failed each time — Q2 succeeded in all runs, Q1/Q3/Q4/Q5 failed in all runs.

**Predictions, both falsified:**

| # | prediction | conf | outcome |
|---|---|---|---|
| 1 | 27B `Q6_K` parses >= 50 % (undamaged, so no `battle16gb` stopping failure) | 0.60 | **FALSIFIED** — 20 %, exactly the 9B |
| 2 | `recommended` sampling parses ~60 % (Qwen names repetition, gives the remedy) | 0.55 | **FALSIFIED** — 20 %, unchanged |

Both wrong in the same direction, and that is the useful part: twice a configuration fix was
proposed for a result the per-question data already said was config-independent. The pattern
worth recording is reaching for a fixable cause rather than the simpler one.

**What remains.** Model size, quant tier and sampling profile are all eliminated. The only
variable common to all three runs is the **12288-token budget** — against Qwen's own
recommendation of 262,144 reasoning tokens for this model, i.e. we run at 4.7 % of it. The
successes support this: they finish well under budget (3400, 6673, 7316 tokens) while every
failure hits 12288 exactly. That bimodality is a hard ceiling, not a distribution crowding one.

**Incidental confirmation.** `recommended` was 17 % slower than `deterministic` (716 s vs
612 s per question) at identical token counts. Expected: greedy output is maximally
predictable, so it draws the highest draft acceptance, and temp 1.0 / top_k 20 lowers it. Same
content-predictability mechanism measured in `qwen35-drafters` — speculation pays for
diversity.

**Qwen's own number is 30.8**, with the complete disclosed methodology being "HLE: Judged by
GPT-4o" — no budget, no sampling, no tool/search statement, no run count. Not reproducible
from what is published, which is the same criticism this campaign levelled at a packager chart
and applies here equally.

**Next test, and it is decisive:** re-run only the questions that failed, at a much larger
budget. If they close at 32k–64k, the budget is confirmed and HLE-mini is viable on this fleet
at a known cost per question. If they still truncate, the model genuinely cannot close them
and no budget will help.

## THE FIX (2026-08-16): reasoning_effort, not budget, sampling, model size or quant

`reasoning_effort` is a **chat-template variable**, not a sampling parameter or a server flag.
From the GGUF's own template:

```
raise_exception('Unexpected reasoning effort ... Supported types are xhigh (default),
                 medium, and low.')
```

`xhigh` is the **default**, and its injected system text is *"think carefully through the
task, validate key assumptions, consider plausible alternatives"*. `low` is *"Keep your
thinking brief and focused, moving directly to the conclusion without unnecessary
elaboration."* Every run before this one sent no system prompt, so every run was `xhigh`:
a model instructed to consider alternatives, on questions it cannot solve, against a token
cap. It did as told until the cap stopped it.

| run | model | effort | sampling | parse | trunc | median tok | median wall |
|---|---|---|---|---:|---:|---:|---:|
| 1 | 9B `Q8_0` | xhigh | deterministic | 20 % | 80 % | 12288 | 218 s |
| 2 | 27B `Q6_K` | xhigh | deterministic | 20 % | 80 % | 12288 | 612 s |
| 3 | 27B `Q6_K` | xhigh | recommended | 20 % | 80 % | 12288 | 716 s |
| **4** | 27B `Q6_K` | **low** | recommended | **80 %** | **20 %** | **1958** | **82 s** |

Per question, run 4 against the same questions in runs 2–3:

| q | prior (xhigh) | low | confidence |
|---|---|---|---:|
| 1 | truncated x2 | **695 tok, stop** | 5 % |
| 2 | 3400 / 6673 tok | **799 tok, stop** | 85 % |
| 3 | truncated x2 | **4426 tok, stop** | 55 % |
| 4 (MC) | truncated x2 | **1958 tok, stop** | 95 % |
| 5 | truncated x2 | truncated | — |

**Token spend now tracks difficulty** (695 -> 4426) and **confidence discriminates**
(5 % / 85 % / 55 % / 95 %). At `xhigh` the model produced 39,777 characters of reasoning on
Q1 and no answer; at `low` it answered in 695 tokens and correctly flagged 5 % confidence.
Committing an answer and reporting low confidence is the behaviour that makes RMS calibration
error measurable at all — you cannot calibrate a model that never answers.

**Practical consequence.** A full 200-question run drops from the 8.1 h projected at `xhigh`
to roughly **4.6 h**, and the earlier "quantise KV to buy reasoning headroom" plan is
unnecessary: the headroom was never the constraint.

### Caveat, stated rather than buried

Run 4 used a server restarted with `-np 1 --cache-reuse 0` after the previous instance
degraded into emitting `/` characters for an entire budget (see below), so slot configuration
differs from runs 2–3 as well as effort. The effect size (20 % -> 80 %, 6.3x fewer tokens)
is far larger than any plausible slot-config contribution, but a matched `xhigh` arm on the
same clean server is queued and this claim is provisional until it lands.

### A separate failure worth its own entry: server state degradation

Mid-session the `.73` server began returning pure `/` repetition for an entire token budget,
at **both** effort levels, on a prompt that had worked minutes earlier. Restarting fixed it.
Three variables changed in that restart (f16 KV instead of `q8_0`, `-np 1`, `--cache-reuse 0`)
so the cause is **not isolated**. The leading suspect is slot reuse: the server logged
`selected slot by LCP similarity, f_sim_best = 0.136 (> 0.100 thold)`, a very loose bar, and
Qwen 3.6+ preserves thinking blocks rather than stripping them — so a reused slot can condition
one question on another's reasoning. If instead the cause is `q8_0` KV on Pascal, that is a
hardware finding and it kills the KV-quantisation-for-headroom idea. Unresolved; worth one
isolation run.

Had the degraded instance not been caught, run 4 would have been reported as "low effort
does not help either" — a false null on the one lever that works.

### Controlled confirmation (2026-08-16)

The `low` result above was run on a server restarted mid-session, so effort was confounded
with slot configuration. A matched `xhigh` arm was then run on that same clean server:

| arm | effort | parse | trunc | median tok | median wall |
|---|---|---:|---:|---:|---:|
| `q38_low_clean` | **low** | **80 %** | 20 % | **1958** | **82 s** |
| `q38_xhigh_clean` | xhigh | **0 %** | 100 % | 12288 | 721 s |

Identical server, slot config, sampling profile, question set and token budget. Only
`reasoning_effort` differs. **0/5 against 4/5**, Fisher exact p ~= 0.024 one-tailed;
6.3x fewer tokens and 8.8x less wall time. The confound is removed and the finding stands.

Note the control scored *worse* than the three earlier `xhigh` runs, which each closed Q2.
That is expected: `recommended` sampling is `temperature 1.0`, so runs are genuine draws
rather than replays, and single-run parse rates carry real variance. **The 80 % figure is one
draw and could be 60 % or 100 % on a repeat** — unlike the deterministic replays in `headlab`,
repeats here would be independent samples and are worth taking. Any published parse rate needs
repeats behind it.

### Accuracy is still unmeasured, and it is the live question

Post-hoc judging of saved traces (`rejudge.py`, local judge on the idle 9070 XT):

| trace set | effort | parsed | correct |
|---|---|---:|---:|
| `q38_q6k` | xhigh | 4 | 0 |
| `q38_q6k_rec` | xhigh | 5 | 1 |
| `q38_low_clean` | **low** | 4 | **0** |

`low` terminates far more often and has not yet been shown to *answer* more often. Mark's
hypothesis — that `medium` is the sweet spot because `low` buys termination by giving up — is
live and untested. Q1's self-reported 5 % confidence at `low` is consistent with giving up
honestly rather than solving. At n=5 none of this is resolvable.

**Judge caveat.** The judge is Qwen3.5-9B with free reasoning and a parsed `VERDICT:` line.
A one-token grammar-constrained verdict was tried first and is a **YES-machine** — it returned
YES for `Paris` vs `Berlin`. Forcing an immediate answer from a reasoning-tuned model destroys
its judgement, and the failure is invisible without a known-negative control. The reasoning
version validated 5/6, its one miss being strict (`Frits Zernike` vs `Zernike` -> NO), so it
biases scores **down**. Judged numbers from it are floors.

**Also unresolved:** `run_hle_mini.py` parses `content` only; `rejudge.py` parses
`content + reasoning` and therefore reports 40-50 % parse where the runner reports 20 %. The
stricter reading is probably right — a truncated response's reasoning contains *drafts*, not
conclusions — but two tools disagreeing about the same traces must be reconciled before either
number is quoted anywhere.
