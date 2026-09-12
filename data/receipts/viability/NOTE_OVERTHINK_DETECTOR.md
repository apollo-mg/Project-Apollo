# Note — thinking length as a runtime confabulation detector, and the corpus that would falsify it

**2026-09-11. Analysis only, no new run.** Data: `card_xhigh_rep{1,2,3}.jsonl`
(`Qwen3.8-27B-Q6_K`, `.194`, card sampling, seeds 1001–1003) — the same 48 traces behind
`RESULT_SEARCH_ASYMMETRY.md`. Exploratory, not pre-registered.

**The idea** (Mark, in conversation): if confabulation runs longer than abstention, a harness could
watch thinking length at runtime and escalate — *"are you overthinking this, or is it a real
confound? call an advisor."* This note asks whether the signal is strong enough to act on.

## On this corpus the separation is nearly clean

At `xhigh`, thinking characters by arm and outcome:

| arm | outcome | n | median | min | max |
|---|---|---|---|---|---|
| answerable | ANSWERED-CORRECT | 24 | **572** | 303 | 845 |
| unanswerable | ABSTAINED | 13 | 2,351 | 859 | 12,281 |
| unanswerable | ANSWERED-WRONG | 6 | 4,196 | 677 | 14,532 |
| unanswerable | NO-STOP/REC | 5 | **26,601** | 24,036 | 28,236 |

**Best single threshold: ≥ 1,000 characters catches 82% of failures and flags 0% of correct
answers** (Youden J = 0.82).

Two further points in its favour:
- **The within-item control already holds.** `RESULT_SEARCH_ASYMMETRY.md` shows 3 of 3 mixed-outcome
  items running 2.15–10.87× longer when failing, with the item and effort held fixed. The signal is
  not merely item difficulty.
- **The loudest band is a distinct mode.** NO-STOP at ~26,600 characters is an order of magnitude
  above everything else and is already independently detectable as a cap hit.

## The reason this is not yet a detector

**Our answerable arm is easy.** All 24 are correct, median 572 characters, maximum 845 — the model
never has to work hard to succeed here. The threshold separates so cleanly because nothing in the
corpus is *hard and answerable*.

That is precisely the case which would break it. `RESULT_SEARCH_ASYMMETRY.md` reconciles our numbers
with AA-Omniscience by noting that on AA's corpus — **accuracy 16–21%, so genuinely hard, and every
question has an answer** — more deliberation *helps*. A hard answerable question should therefore
produce long thinking **and** a correct answer, which is exactly a false positive for this rule.

Already visible at the bottom edge: **6 of 24 correct answers think longer than the shortest
confabulation** (677 characters). The tails overlap even in the easy case.

**The sign also flips with effort.** From the same receipt: at `medium` and `low`, failures are
*shorter* than abstentions (0.42–0.56×) — the model answers before deliberating instead of talking
itself into an answer. A one-sided "long means trouble" rule is backwards at two of the three effort
settings.

## What would make it real

1. **Calibrate against hard-but-answerable items.** The decisive test is whether thinking length
   separates *confabulation* from *legitimate hard work*. Needs a corpus like AA-Omniscience's, where
   accuracy is 16–21% and answers exist. Until that is run, the 82%/0% figure describes an easy
   answerable arm and should not be quoted as a detector's accuracy.
2. **Make the rule two-sided and effort-aware.** Flag both tails: unusually long at `xhigh`,
   unusually short at `medium`/`low`. A single global threshold is wrong by construction.
3. **Prefer the within-item form where affordable.** Resample the same prompt twice and compare:
   `CAL-U8` produced 2,351 characters when it abstained and 24,036–27,096 when it confabulated. A
   large *spread* across resamples of one prompt is a stronger signal than any absolute length, and
   it needs no cross-item calibration.

## Why it is worth building even at 82%

The cost asymmetry favours a permissive threshold. **A false positive costs one advisor call. A
false negative costs a silent wrong answer delivered at full confidence** — the failure mode that
`RESULT_LOCAL_VLM_GRADER.md` caught tonight, where a 3-bit judge scored a drawing with a visibly
floating head at 7/10 with no error, no retry and no slowdown.

This is also the general form of the open question in that campaign: **what fraction of
quantisation-induced errors are harness-detectable?** Thinking length is one candidate channel for
converting a silent failure into a loud one.
