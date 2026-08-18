# HLE-mini — project status and what to do next

**2026-08-18.** Assessment of the whole harness, not a run report. Aggregate statistics only;
no question text, answer text, or per-question outcomes, per the HLE content-hygiene rule.

## Headline: the harness has never produced an interpretable accuracy number

Across all 8 runs to date — **65 rows total** — the reported accuracy is **0.00 everywhere**.
That figure is not a measurement of model capability. Breaking the rows down by how they
actually terminated:

| `graded_by` | answer parsed? | finish | n | what it means |
|---|---|---|---:|---|
| `needs_judge` | no | `length` | **36** | ran out of tokens, said nothing gradeable |
| `mc` | no | `length` | **8** | same, multiple-choice item |
| *(none)* | no | — | 8 | row never completed |
| `needs_judge` | **yes** | `stop` | **9** | **answered, and was never graded** |
| `needs_judge` | **yes** | `length` | 1 | answered, never graded |
| `mc` | **yes** | `stop` | 3 | **genuinely graded** — wrong |

**Exactly 3 of 65 rows were ever actually adjudicated.** 44 were truncated before emitting an
answer, and 10 produced a parsed answer that was silently scored wrong because no judge ran.

**Correction to the working memory of this project:** the "2/10 with Qwen" figure is the
**parse rate**, not a score. The accuracy has been 0/N in every run. And comparing anything
here to *"Qwen's 40 on the full suite"* is invalid twice over — different question set, and
we have not yet measured a score at all.

## Two blockers, both known at design time, both cheap to fix

### 1. The token budget was always below the documented minimum

`build_subset.py`'s own docstring states: *"the official harness wants **>=8192 completion
tokens** per item to avoid truncation."* Every run so far:

| run | budget | truncated |
|---|---:|---|
| `budget_1024` | 1024 | 8/10 |
| `budget_2048` | 2048 | 9/10 |
| `budget_4096` | 4096 | 1/2 |
| `q38_q6k` | default | 8/10 |
| `q38_xhigh_clean` | default | **5/5** |
| `q38_low_clean` | default | **1/5** |

**We ran at ⅛ to ½ of the documented minimum.** `RESULT_B2_PARSE_RATE.md` established the
parser is not at fault — among responses that *finish*, it succeeds **12/12 = 100 %**. The
"22.8 % parse rate" was the **79 % truncation rate** wearing a parser's clothes.

Note the effort dial dominates: `xhigh` truncated **5/5**, `low` truncated **1/5**. Reasoning
effort and token budget are the same axis here, and neither was ever set high enough.

### 2. The judge was never configured, and its absence scores answers as wrong

`run_hle_mini.py:197` grades by exact string match, then falls through to
`judge_equivalent()` **only if `--judge-host` (or `JUDGE_HOST`) is set**. It never was —
`judge_calls: 0` in every result file. Without it, any answer that is semantically right but
not byte-identical to the gold string is labelled `needs_judge` and **counted as incorrect**.

HLE answers are short free-text; exact match is not a viable grader. **10 of our 65 rows are
sitting in that bucket right now.** The judge is a local model call — free on this fleet.

## What is actually in good shape

- **Subset construction is sound and hygienic.** `build_subset.py` writes **IDs only**, seeded
  and reproducible, `text_only`, with `id_set_sha256` recorded in every result file. 200 IDs
  selected; `screen_v1` is a nested subset with `parent_id_set_sha256` linking it. This
  respects the HLE canary request properly.
- **The design goal is the right one, and it is not "beat 40 %".** The docstring is explicit:
  the subset exists to measure **quantisation deltas**, where every arm sees identical
  questions, and *"any result from this MUST be labelled a subset score, never 'our HLE
  score'."* Chasing the published number was never the plan and should not become it.
- **Traces are stored per run**, which is what made the B2 diagnosis possible without re-running
  anything.

## A validity threat worth designing against now

If the goal is quantisation deltas, **truncation rate is itself quant-sensitive** — a weaker
quant that rambles will truncate more, so a naive accuracy comparison would conflate
*knowledge* with *verbosity*. The `xhigh` 5/5 vs `low` 1/5 split shows how strongly this axis
moves.

**Mitigation:** report truncation rate as a first-class outcome alongside accuracy, and
either (a) set the budget high enough that truncation is near zero in every arm, or
(b) treat truncation as a failure mode of the arm rather than excluding it from the
denominator. Excluding truncated items would bias every arm toward the questions it happened
to finish — a selection effect pointing the same way as the score.

## Recommended order

1. **Set `--judge-host`** to a local endpoint and **re-grade the existing traces**. Costs one
   pass over stored data, no generation. Converts 10 ungraded rows into real outcomes and
   tells us whether the harness can score *anything* correctly. **Do this first — it is
   minutes, and it is the only step that can be done without any GPU generation.**
2. **Raise the budget to the documented ≥8192** and re-run the 10-question set. Yields the
   first accuracy number this project has ever had. At ~29 t/s that is roughly 45 min for 10
   questions.
3. **Widen the sample.** 10 questions cannot separate 20 % from 40 % — the binomial interval
   at n=10 is roughly ±30 pp. 30–50 items is the minimum for a usable comparison, and the
   200-ID subset already exists.
4. **Only then compare arms.** Quantisation deltas are the actual product, and they are
   uninterpretable until steps 1–3 make a single arm meaningful.

Full HLE is explicitly out of scope on this fleet — `build_subset.py` estimates **150–450
hours per arm** at the official budget, which is why the subset exists.
