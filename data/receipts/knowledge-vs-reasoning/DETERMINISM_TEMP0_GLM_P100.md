# Temp-0 greedy decoding is not reproducible on this build (714-probe measurement)

**Date:** 2026-08-06. **Purpose:** fix `K` for the Phase 1 comparison by measuring reproducibility
directly rather than waiting on a third-party claim.
**Result:** two identical runs differ. **K = 1 is not justified.**

## Configuration — the easiest possible case

Both runs used the *same live server process*, same model file, same flags, back to back:

| field | value |
|---|---|
| model | `GLM-4.7-Flash-Q6_K.gguf` (base arm) |
| build | `~/tom_default/build/bin/llama-server`, `b100-0967f4997` (TheTom fork) |
| node | `.73`, 2 × Tesla P100-PCIE-16GB, 1063 MHz / 150 W |
| server | `-c 4096 -ngl 99 -sm layer -np 1 --jinja -v` |
| client | `temperature 0`, `max_tokens 64`, `concurrency 1`, `enable_thinking: false` |
| probes | IKP T1–T4, `--exclude-source researcher`, **714** |
| runs | `ikp_glm_base.jsonl` (432 s) and `ikp_glm_base_rep2.jsonl` (276 s) |

`-np 1` with one request in flight means **no batch-composition effects** — the usual explanation for
temp-0 nondeterminism is excluded by construction. This is the configuration most likely to be
reproducible, and it is not.

## Instability at three levels

| level | result |
|---|---|
| **response string** | 697/714 identical, **17 differ (2.38%)** |
| **`completion_tokens`** | 15 of those 17 also differ in length |
| **scored verdict** | **8/714 flip (1.12%)** |
| **aggregate accuracy** | **identical** — 490 / 130 / 92 / 2, 68.6%, penalized 0.504 |

Some of the 17 are cosmetic and do not change the verdict — markdown drift such as `**1967**` vs
`1967`, or `*Journal of Paleontology*` vs plain. Others are outright different facts:

```
Shanghai Normal University founded?   run1 "1954"   run2 "1905"
Journal Analysis first published?     run1 "1954"   run2 "1934"
Transportation Journal first pub?     run1 "1966"   run2 "1960"
University of Advancing Technology?   run1 "1991"   run2 "2004"
```

## Where the instability lives, and why it matters

| tier | verdict flips | rate |
|---|---|---|
| T1 | 0 / 200 | 0.00 % |
| T2 | 0 / 200 | 0.00 % |
| T3 | 1 / 165 | 0.61 % |
| **T4** | **7 / 149** | **4.70 %** |

Flips concentrate almost entirely in **T4**, the most obscure tier — where the model is least
certain and the top-1 logit gap is smallest. A near-tie flips on a tiny numerical difference. That is
mechanistically sensible and it means **the noise is worst in exactly the tier the thesis cares most
about** (tail knowledge).

The transitions are almost perfectly balanced, which is why the aggregate hides them:

```
CORRECT -> WRONG    2        WRONG -> CORRECT   2
REFUSAL -> WRONG    2        WRONG -> REFUSAL   2
```

Per-tier accuracy therefore moves while the total does not:

| tier | run 1 | run 2 | Δ |
|---|---|---|---|
| T1 | 92.0 % | 92.0 % | 0.0 |
| T2 | 88.0 % | 88.0 % | 0.0 |
| T3 | 57.0 % | 56.4 % | −0.6 pp |
| T4 | 24.2 % | 24.8 % | +0.6 pp |
| **ALL** | **68.6 %** | **68.6 %** | **0.0** |

**Reporting only the aggregate would have shown a perfectly reproducible measurement.** It is not.

## Consequence for K

Observed per-tier movement between two identical runs is **≈0.6 pp**. Per §7, N=2 is an existence
proof of instability and a rough magnitude — **not** a variance estimate, and no σ is claimed here.

**K = 5 per arm**, reporting mean and range per tier, with the paired delta taken across matched
runs. At ~5 minutes per arm that is ~50 minutes for both arms — affordable.

P-R2 predicts a ≥5 pp drop on T3+T4. Against ~0.6 pp of observed per-tier noise that is roughly an
8× margin, so the predicted effect remains detectable. But a claim of *no* change on any tier would
need K≥5 and an explicit `n_observed / n_runs`, because at T4's 4.7% flip rate a single run can move
that tier by ~0.6 pp for free.

## Relation to buun's determinism claim — stated carefully

On 2026-08-04 buun wrote *"with 0 temp (argmax) it will spit the same answer out every time"* and
separately *"I did fix those determinism issues"*.

**This measurement does not contradict the second statement.** His fix is in *his* fork; this ran on
`tom_default` (TheTom's fork at `0967f4997`). What it establishes:

1. The first statement is **false as a general claim about greedy decoding** — argmax is deterministic
   given identical logits, but the logits themselves are not stable run to run.
2. The defect is **live on the build this lab is measuring with**, in the easiest configuration.
3. There is now a **concrete, cheap reproducer** — 714 probes, ~5 minutes, binary pass/fail on
   `17 differ` — to point at his fork and check whether the fix holds. That is worth more than
   agreeing or disagreeing in chat.

It also corroborates the earlier HA-04 result (`35 / 100 / 100 / 35` at temp 0 on `.73`) on a
completely different workload and model, which makes a workload-specific explanation less likely.

## Limits

- **N = 2.** Existence proof and rough magnitude only. No σ, no confidence interval.
- Same server process for both runs, so accumulated prompt-cache state is shared. A cold-start
  replicate is the stricter test and has not been run.
- One model, one build, one node. Says nothing about other architectures or about `-np > 1`, which
  should still be assumed worse.
- Does not identify the mechanism. Candidates not distinguished here: non-deterministic GPU
  reductions, MoE routing flips on near-tied gate values, or scheduling-dependent accumulation order.
  The T4 concentration is consistent with near-tie sensitivity anywhere in that chain.
