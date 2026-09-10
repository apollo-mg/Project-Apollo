# Deliberation is a search: it helps when a target exists and hurts when it does not

**Date:** 2026-09-07 · **Data:** `card_{xhigh,medium,low}_rep{1,2,3}.jsonl` (2026-08-21 / 09-07)
`Qwen3.8-27B-Q6_K`, `.194`, card thinking sampling, seeds 1001–1003. **Analysis only — no new run.**

## The observation

Within the unanswerable arm, trace length predicts the outcome, and the sign flips with effort:

| effort | abstained, median chars | failed, median chars | ratio |
|---|---:|---:|---:|
| `xhigh` | 2,351 (n=13) | **14,532** (n=11) | **6.18×** |
| `medium` | 792 (n=21) | 440 (n=3) | 0.56× |
| `low` | 739 (n=21) | 312 (n=3) | 0.42× |

**Within-item control.** Item difficulty could explain that on its own — hard items may both
run long and fail. For items with *mixed* outcomes at `xhigh` (same question, same effort,
same sampling; only the sampled trajectory differs):

| item | abstained | failed | ratio |
|---|---|---|---:|
| `CAL-U4` | 2920, 2863 | 7307 | 2.53× |
| `CAL-U5` | 5808 | 14532, 10431 | 2.15× |
| `CAL-U8` | 2351 | 27096, 24036 | **10.87×** |

**3 of 3 items longer when failing.** Difficulty is held fixed, so the raw correlation is not
merely an item-difficulty artifact.

At `medium` and `low` the relationship inverts: failures are *shorter* (0.42–0.56×). No item
had mixed outcomes at those levels, so no within-item control is available there. The failures
at those settings are `CAL-U3`, which answers in 312–440 characters — a snap judgement, a
different failure mode from `xhigh`'s.

## Two failure modes, not one

- **`xhigh`: talks itself into an answer.** 14,532 characters of deliberation before producing
  a confabulation. `CAL-U8` reached 27,096.
- **`medium`/`low`: answers before deliberating.** 312–440 characters, straight to a confident
  wrong answer.

The fixture currently books both as `ANSWERED-WRONG`. They are not the same defect and a
corpus that cannot distinguish them will mis-attribute the cause.

## Why this reconciles our data with Artificial Analysis

AA-Omniscience reports Qwen3.8-27B hallucination as `xhigh` **30 %**, `low` 53 %, `medium` 67 %
— `xhigh` best. Our fixture finds `xhigh` worst (confabulation 6/24 vs 3/24). Two earlier
reconciliation attempts failed (mechanism split; NO-STOP scored as "not attempted" — see the
A1 spec amendment).

**This explains it, and both measurements can be correct:**

| corpus | do the questions have answers? | effect of more search |
|---|---|---|
| AA-Omniscience | **yes**, all of them (accuracy 16–21 %, so they are hard) | finds the answer more often → `xhigh` wins |
| our unanswerable arm | **no**, none of them | manufactures an answer more often → `xhigh` loses |

Deliberation is a search process. Search terminates on a hit when a target exists; when none
exists it runs until something is constructed. `A5` recorded the same asymmetry from the cost
side — the unanswerable arm costs 4–9× its partner *because* proving a negative means
exhausting a search.

So `xhigh` is not miscalibrated. It is tuned for the regime where a target exists, and our
unanswerable arm is the regime where that tuning is exactly wrong.

## Prediction this makes

On **hard-but-answerable** items — the arm `A1` now specifies and our fixture lacks — `xhigh`
should **beat** `medium`, reversing the result on the unanswerable arm. If it does not, this
account is wrong and the AA disagreement returns unexplained.

That is the cheapest available test of this receipt, and it needs the A1 third arm to exist.

## Limits

- **3 items with mixed outcomes, 1–2 observations per cell.** Consistent in direction, thin
  in quantity.
- **Co-occurrence, not causation.** Within an item, a long trace and a failure co-occur. An
  unlucky early token could produce both. "Long deliberation causes confabulation" and "an
  early wrong turn causes both the length and the failure" are **not** separated by this data.
  Distinguishing them needs intervention — truncating deliberation at a fixed budget and
  measuring the outcome — not more observation.
- Characters, not tokens (`run_fixture.py:216`).
- One model, one quant, one node, one fixture.
- The AA figures are third-party and their measured-vs-estimated status is unresolved
  (`NOTE_AA_OMNISCIENCE_LINEAGE.md`). This receipt explains a disagreement that may not exist.
