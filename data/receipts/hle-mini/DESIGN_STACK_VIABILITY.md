# Stack-viability fixture — design, and why it is not a benchmark

**2026-08-18.** Supersedes the benchmark framing of `hle-mini`. Per Mark:

> *"This test isn't HLE-mini anymore, it's HLE-inspired 'do we have a working inference stack
> with a half decent model' test. It's meant to save us time, not compare performance."*

That reframe is correct, and the statistics below show it was also **forced** — the current
question set cannot do the job it was being asked to do, at any sample size.

## Three questions, answered

### 1. "Did it know the answer and fail to articulate?" — **No.**

Mechanical check over all stored traces: does the normalised gold string appear **anywhere**
in the model's output, including the full reasoning?

| | n | gold present anywhere |
|---|---:|---:|
| gradeable responses (gold long enough to test) | 9 | **0** |
| truncated responses (gold long enough to test) | 30 | **0** |

The model never reaches the answer — not in the final line, not mid-reasoning. So the failure
is **not** articulation, and **not** "got lost after finding it". Those two hypotheses are
dead. *Limitation: exact substring matching; a semantically-equivalent phrasing would not
match, and 18 golds were under 3 characters and untestable this way.*

### 2. "How many samples to claim X?"

**Rule of three** — with **zero** successes in n, the 95 % upper bound on the true rate is 3/n:

| n | rules out a true rate above |
|---:|---|
| 13 *(what we have)* | 23 % |
| 30 | 10 % |
| 60 | 5 % |
| 300 | 1 % |

**Comparing two arms** (the original quantisation-delta goal), α=.05, power=.80:

| to detect | n per arm |
|---|---:|
| 40 % vs 20 % | **82** |
| 20 % vs 10 % | **199** |
| 40 % vs 30 % | **356** |
| 95 % vs 60 % | **22** |

At HLE difficulty, a quant comparison needs **hundreds of items per arm**. At ~2.5 h/question
for the recommended budget that is not a fleet problem, it is an arithmetic impossibility.
**Note the last row**: the same comparison becomes cheap when the base rate is high — which is
the entire argument for changing the question set rather than the sample size.

### 3. Why hard questions cannot gate a viability test

A viability gate must pass a working stack and fail a broken one. Modelling "working" and
"broken" as different success rates, with a **threshold** gate (not "≥1 correct", which is a
bad gate and separates poorly):

| question difficulty | gate | working passes | broken passes | |
|---|---|---:|---:|---|
| easy (95 % / 10 %) | ≥4 of 5 | **97.7 %** | **0.0 %** | excellent |
| medium (80 % / 15 %) | ≥6 of 10 | **96.7 %** | **0.1 %** | excellent |
| **hard (15 % / 5 %)** | ≥1 of 5 | 55.6 % | 22.6 % | **useless** |
| **hard** | ≥4 of 30 | 67.8 % | 6.1 % | **useless** |

**When a working stack itself only scores 15 %, no threshold separates it from a broken one,
and more samples do not fix it** — the signal is small because the *ceiling* is small. A
30-question HLE gate would wrongly fail a healthy stack about a third of the time.

**Five easy questions do the job better than thirty hard ones.** That is the design.

## What the fixture should be

Three tiers, each answering a different question, each with its own gate. Only tiers 1-2 are
gates; tier 3 is a thermometer and is never allowed to block.

| tier | purpose | difficulty target | n | gate |
|---|---|---|---:|---|
| **1 — plumbing** | server up, template applied, tokens flowing, format obeyed, judge functional | trivial; any working model ≈100 % | 5 | **5 of 5** |
| **2 — model sanity** | weights/quant/sampling not degraded | moderate; decent model 80-90 % | 10 | **≥6 of 10** |
| **3 — headroom** | how much capability is left | genuinely hard | 10-20 | **report only** |

**Tier 1 is the one that would have caught every bug this project has hit.** Truncation at
1024 tokens, the unset judge host, the draft-scraping parse — all of them fail a
five-question trivial fixture immediately and unambiguously, and all of them survived months
of real runs because the questions were hard enough that failure looked like difficulty.

Design constraints for the items:

- **Short, unambiguous, single-token-ish gold answers**, so exact match works and the judge is
  a backstop rather than the primary grader.
- **Bounded reasoning** — an item that needs 8k tokens to answer cannot test plumbing, it
  tests budget. Tier 1 items must be answerable in a few hundred tokens.
- **Known-negative controls included.** At least one item where the *right* behaviour is to
  refuse or say unknown, so a yes-machine fails. `rejudge.py`'s docstring records exactly this
  failure mode in the judge itself (`Paris` vs `Berlin` → YES from a one-token verdict).
- **Written by us, not drawn from HLE.** Answers HLE's public-sample question directly: HLE
  does publish sample items, but **we do not want HLE-difficulty questions for tiers 1-2** —
  that difficulty is precisely what destroys the gate. Writing our own also sidesteps the
  canary/contamination concern entirely.

## What this fixture will and will not license

**Will:** *"the stack is working"* / *"the stack is broken"*, in minutes, reproducibly, with
the exact sampling parameters, system prompt, and inference-stack options recorded — which is
the thing actually under our control and the thing that most often explains a bad number.

**Will not:** any statement of the form *"model X can/cannot do Y"*. That needs the sample
sizes in §2 and is out of reach here for hard benchmarks. The correct posture, and the one
worth staking a name to, is: **we can show a model was given a fair chance, and we can show
exactly what it was given.** That is a claim about *our* rigour, not about the model's ceiling,
and it is fully defensible.

## A caution about the numbers we are comparing against

Published figures like *"Qwen scored 40 on HLE"* arrive through several transformations —
a lab's internal harness, a marketing summary, a social-media restatement, and often a
language boundary. Before treating any such number as a target we should establish **what was
actually claimed**: which subset, which judge, which reasoning budget, how many samples, and
whether the figure is text-only or multimodal. A claim can look stronger or weaker than it was
meant to purely through restatement, in both directions.

Concretely: our fleet cannot reproduce a 260k-token reasoning budget, so any comparison to a
number produced under one is not a like-for-like disagreement — it is a different experiment.
Saying so plainly is more useful than either matching the number or disputing it.
