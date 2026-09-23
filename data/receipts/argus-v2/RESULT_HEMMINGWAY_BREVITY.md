# Hemmingway is terse by nature, not just better at obeying a brevity prompt

**2026-09-23 (run overnight 21:26-02:30). `.194`, reference configuration.** Answers
`PREREG_HEMMINGWAY_BREVITY.md`. 2x2 (stock Qwen3.8-27B / Hemmingway-1, both bartowski Q5_K_M x
brevity `SOUL.md` / none), 2 reps x 40 items per cell, all four cells fresh under the sandboxed
harness. Order counterbalanced, servers restarted per phase, `/props` verified at every launch.
Analysis: `tools/argus_brevity_2x2.py` (the prereg's method, saved). Raw: `raw_brevity_*.jsonl`.
Clean run: 0 INFRA, 0 tripwires, 0 deny blocks, 0 hard stops in any cell. **The sandbox held:**
models tried to explore the home directory 3 times (`ls ~`, `ls ~/Downloads`, a search for the
landlord's name on the `f2-lookup` rent item that triggered the real-disk searches before) and saw
an empty home each time. Teardown verified
`.194` chassis off at 02:31.

## Answer

**Without any explicit brevity instruction, Hemmingway still writes about 27 % shorter replies and
reasons about 27 % less than stock, and the gap is statistically the same as with the instruction.**

| reply length (per-item geometric, paired) | H / S | 95 % CI | p |
|---|---:|---|---:|
| **R+** with the brevity prompt | **0.67x** | [0.58, 0.78] | <0.0001 |
| **R-** without it | **0.73x** | [0.61, 0.87] | 0.0008 |
| **interaction** R- / R+ | 1.08x | [0.86, 1.34] | 0.51 |
| stock: no prompt / prompt | 1.33x | [1.14, 1.54] | 0.0005 |
| Hemmingway: no prompt / prompt | 1.43x | [1.23, 1.66] | <0.0001 |

The prompt works on **both** models, lengthening each by a third or more when removed. The
Hemmingway/stock gap barely moves (0.67x -> 0.73x). A compliance story predicts the gap closing when
the instruction is removed. It stays open: at the point estimate about 78 % of the effect survives
without the prompt, and the remaining movement is indistinguishable from zero.

| reasoning length | H / S | 95 % CI | p |
|---|---:|---|---:|
| R+ with prompt | 0.80x | [0.69, 0.92] | 0.003 |
| R- without | 0.73x | [0.62, 0.87] | 0.0009 |
| interaction | 0.92x | [0.74, 1.15] | 0.46 |

Tool calls are unchanged in every comparison (0.93-0.99x, all p > 0.1). It does the same work and
says less.

## What "no prompt" means here

The no-`SOUL.md` cells ran on Hermes's built-in identity, which itself says *"prioritize being
genuinely useful over being verbose unless otherwise directed ... Be targeted and efficient."* So
the contrast is **strong explicit brevity instruction vs. Hermes's mild default**, not instruction
vs. nothing. That still discriminates the two stories. Halving the pressure lengthened both models
substantially while leaving the gap between them in place, which is what an intrinsic register
looks like. A literally empty system identity would need a Hermes patch and was not run.

## Predictions

| id | prediction | conf | outcome |
|---|---|---|---|
| B1 | R+ below 0.90x | 0.85 | **CONFIRMED** (0.67x), replicating the original 0.77x under the new harness |
| B2 | removing the prompt lengthens stock > 1.2x | 0.75 | **CONFIRMED** on the point estimate (1.33x; CI lower bound 1.14x) |
| B3 | without the prompt Hemmingway still terser (CI excludes 1) | 0.55 | **CONFIRMED** (0.73x, CI [0.61, 0.87]) |
| B4 | the gap narrows without the prompt | 0.50 | **Not established.** Point estimate narrows by 8 % (not falsified by its letter), p = 0.51. The prereg called even a half-move borderline at this n; this is far smaller |
| B5 | reasoning cut uneven across families | 0.40 | **Nominally CONFIRMED, exploratory and noisy** (below) |

**Decision, by the prereg's rule:** B3 true with B4 not established -> **intrinsic.**

## Exploratory: where Hemmingway thinks less (n = 6-10 per family, noisy)

H/S reasoning ratio pooled over both prompt conditions: referent `f1` 0.98x and conflict `f5`
0.96x, i.e. **no cut on the two families built around ambiguity between people and times**;
inconsistent `f6` 0.62x and lookup `f2` 0.68x show the largest cuts; the rest are 0.72-0.81x. That is
**not** the Swift pattern (INDEX L43, where a brevity tune cut thinking on false premises); the
premise family `f9` here sits at the average (0.74x). Suggestive only.

## Judgement (reported, not tested; 2 reps cannot resolve anything below the ~10-point floor)

Non-gate pass rate (judge rule): stock+prompt 79.0 %, Hemmingway+prompt 71.0 %, stock no prompt
75.8 %, Hemmingway no prompt 74.2 %. Consistent with the 4-rep result of no detectable difference.

## Caveats

- 2 reps, one corpus of agentic replies. This measures the **register of an agent's reports to
  its user**, not creative or long-form writing, which is what the model is for.
- The environment-variable strip went live 13 minutes into phase 1, equally for both cells; no
  model-facing effect expected (prereg amendment).
- Wall time was deliberately not analysed: the 9B gate shared the desktop for part of the run.
