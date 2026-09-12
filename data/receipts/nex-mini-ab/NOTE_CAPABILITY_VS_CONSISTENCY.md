# Note — the finetunes did not give up capability, they gave up reliability; one retry erases the deficit

**2026-09-12, post-hoc analysis of the three-way panel** (`RESULT_THREE_WAY.md`). **Not
pre-registered** — this is exploratory analysis of data collected for a different question, prompted
by Mark's hypothesis that a heavy finetune "gives up something (probably advanced math, physics, and
creative prose) to get the improvements elsewhere." It should be read as a hypothesis to test, not a
result. All numbers are re-derivable from `results/*.json`.

## The hypothesis, and where the data disagrees with it

A capability trade would show up as problems the finetune **cannot** solve. It does not. Counting
problems solved *at least once* in 3 samples:

| arm | pass@1 | solved ≥1 of 3 | all 3 | **never** | flaky |
|---|---|---|---|---|---|
| QWEN_R1 *(stock base)* | **94.11%** | 95.12% | 151 | **8** | 5 |
| ORNITH_R2 | 90.65% | 95.12% | 142 | 8 | 14 |
| NEX_R1 | 89.84% | **96.95%** | 132 | **5** | 27 |
| NEX_R2 | 86.99% | 96.34% | 122 | 6 | 36 |

**NEX has the best coverage of any arm and the worst pass@1.** It is never-solves on 5 problems
against the base's 8, and it solves **5 problems the base never solves** (the base solves 2 that NEX
never does; 3 are hard for both). The true hard core — never solved by any of the four arms — is 3
problems.

So on this benchmark the finetune did not lose the ability to produce correct code. It lost the
ability to produce it **on demand**. Of the 23 problems where NEX scores below QWEN, **21 are
problems NEX solves at least once**, and 14 of those are a single sample short (2/3 vs 3/3):

| NEX vs QWEN | problems |
|---|---|
| 0/3 vs 3/3 — a genuine capability gap | **2** |
| 1/3 vs 2/3 | 2 |
| 1/3 vs 3/3 | 5 |
| 2/3 vs 3/3 — one sample short | **14** |

**Mark's hypothesis is right that something was traded and wrong about what.** The trade is not a
domain of knowledge, it is determinism. That is also the honest limit of this note: HumanEval+ is
single-function Python, so it tests neither the maths/physics/prose he expects to have been lost nor
the agentic behaviour the finetunes target. A capability trade may well exist in those domains. This
data cannot see it — what it *can* see is that no capability was traded **here**, and reliability was.

## The consequence: a retry harness closes the entire gap

If a harness can detect a failure and retry, the relevant metric is not pass@1. Estimated success by
retry budget, drawn without replacement from the 3 samples we actually collected:

| arm | 1 try | 2 tries | 3 tries |
|---|---|---|---|
| QWEN_R1 | **94.11%** | 95.12% | 95.12% |
| ORNITH_R2 | 90.65% | 93.50% | 95.12% |
| NEX_R1 | 89.84% | **95.33%** | **96.95%** |
| NEX_R2 | 86.99% | 94.31% | 96.34% |
| **NEX_R1 − QWEN_R1** | **−4.27** | **+0.20** | **+1.83** |

**One retry erases the 4.27-point deficit. Two retries beat the base outright** — and the base has
nowhere to go, because its ceiling is its coverage (95.12%) and it is already nearly there at one try.

The token arithmetic makes it stark. At median tokens per completion:

| | tokens | success |
|---|---|---|
| QWEN, one try | 2,408 | 94.11% |
| **NEX, three tries** | **840** | **96.95%** |

**NEX gets a better answer than the base for 35% of the tokens the base spends on a single attempt.**

## Why this matters beyond this panel

This is the clearest quantitative form the campaign has produced of the recurring thesis — *a fuzzier
configuration gets you there most of the time, and the harness hides the errors.* Here the harness
does not merely hide them, it **converts a 4-point loss into a 2-point win** while spending a third of
the tokens. The mechanism is visible: the finetune's failures are concentrated in flaky problems,
which is exactly the failure class a retry is able to recover, and the base's remaining failures are
concentrated in never-solved problems, which no retry budget recovers.

It also reframes what "smarter" should mean for a model aimed at agentic use. NEX's card claims
"significantly smarter"; on pass@1 that is falsified (`RESULT_THREE_WAY.md`, P-T1, p = 0.0023). On
coverage-under-retry it is **true**. Both statements are about the same 1,968 completions.

## What this does not establish

- **Not pre-registered, and post-hoc on data collected for another question.** The prereg's
  registered analysis stands as written; this is a new hypothesis generated from it, and the next
  panel should register the retry metric in advance if it is to be claimed.
- **The retry estimate is resampling, not a live retry experiment.** It draws without replacement
  from K = 3, so it is exact within those three samples and an extrapolation beyond them. A real
  measurement needs a harness loop with K ≥ 5.
- **It assumes an oracle that detects failure.** For HumanEval+ the unit tests are that oracle, so
  the assumption is realistic for code. For work with no automatic check — prose, analysis, most
  agentic judgement — a retry cannot be triggered and none of this transfers.
- **A retry harness would also retry the base.** QWEN's ceiling is 95.12% and it reaches 95.12% at
  two tries; the comparison above gives both arms the same budget.
- **Nothing about the lost domains.** Maths, physics and creative prose are untested here. That
  remains Mark's hypothesis, unexamined.
- **Replicate spread applies to these numbers too.** NEX's two rounds differ by 0.61 points on
  coverage and 2.85 on pass@1; quote ranges, not the better round.
