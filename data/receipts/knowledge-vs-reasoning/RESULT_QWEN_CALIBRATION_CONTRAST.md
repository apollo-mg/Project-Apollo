# Result — general-inclusive calibration does NOT preserve knowledge. Our mechanism claim is falsified.

**Date:** 2026-08-07. `0xSero/Qwen3.6-28B-REAP20-A3B` vs `Qwen/Qwen3.6-35B-A3B`, both GGUF-packaged
by **mradermacher**, Q6_K, `.73` 2×P100 @ 1063 MHz / 150 W, build `tom_default`,
`-c 4096 -ngl 99 -sm layer -np 1 --jinja`, thinking OFF, temp 0, K=1, `--exclude-source researcher`.
`ikp_run.py` / `ikp_score.py` unmodified. Pre-registered in `PREREG_QWEN_CALIBRATION_CONTRAST.md`.

## Headline

| tier | base (committed) | pruned | Δ |
|---|---|---|---|
| T1 | 95.5 % | **79.4 %** | **−16.1 pp** |
| T2 | 93.4 % | 62.2 % | −31.2 pp |
| T3 | 74.7 % | 32.0 % | −42.7 pp |
| T4 | 47.9 % | 8.1 % | −39.8 pp |
| **ALL** | **80.5 %** | **49.1 %** | **−31.4 pp** |

**0xSero calibrated on 5,000 stratified samples explicitly including general data, with fresh
rankings, at 20 % — a *lower* ratio than Cerebras's 25 %. Knowledge collapsed anyway.**

## Prediction scoring (§8)

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-Q0** | GATE — base committed T1 ≥ 85 % | 0.75 | **HELD**, 95.5 % |
| **P-Q1** | HINGE — pruned within 10 pp of base on T1 | 0.55 | **FALSIFIED**, −16.1 pp |
| **P-Q2** | pruned refusal rate < 25 % | 0.60 | **HELD**, 11.9 % |
| **P-Q3** | conditional on P-Q1 | 0.65 | **NOT SCORED** — gate not met |

## Gates

**G-5 tripped and was bounded rather than waved through.** Truncation: base 2.8 %, pruned 7.6 % —
a 4.8 pp spread, over the 2 pp rule. The rule exists because divergent termination can manufacture
an accuracy gap, so the question is whether it can manufacture *this* one:

```
worst case FOR the finding — credit the pruned arm ALL 54 truncated probes as
CORRECT and the base arm none:   pruned 52.9 %  vs  base 78.3 %   ->  +25.4 pp
```

**It cannot.** The effect survives the most generous possible correction by a wide margin. The
committed metric already excludes `NO_ANSWER` by construction; this bound is the belt to that
brace.

**AMBIGUOUS symmetry** — Qwen3.6 answers far more verbosely than GLM did (`"The Strait of Messina
separates Sicily from mainland Italy."` vs `"The Strait of Messina."`), and the grader books
>25-word responses AMBIGUOUS even when correct. Checked: base 2.0 %, pruned 3.4 %, spread 1.4 pp.
Not distorting the denominator.

**G-1 packaging parity** — identical recipe (432 Q6_K + 301 F32), 733 tensors both, **imatrix-free
on both arms**, `expert_count` 256 vs 205 and `n_expert_used = 8` read from the files and again
from the runtime before inference.

> **A first attempt at this pair was discarded.** 0xSero's own GGUFs have the **pruned arm
> imatrix-quantized and the base arm not** — a weight-quality advantage sitting on exactly the arm
> P-Q1 predicted would look good. Caught by G-1 before any inference; both arms re-fetched from a
> single packager. Had it run, a "knowledge preserved" result would have been uninterpretable.

## What this does to the campaign

`CAMPAIGN_SYNTHESIS.md` asserted that **calibration composition governs the damage profile**, on the
strength of one observation. This leg was built to test that by varying it. **The strong form is
falsified:** general data in the calibration set, fresh rankings, and a lower prune ratio together
failed to preserve factual recall.

What survives is weaker and must be stated as such:

- The Cerebras story still explains **why their panel could not see the damage** — every benchmark
  in their retention claim is one they calibrated on. That part stands and is independent.
- It does **not** explain the damage itself. Pruning appears to cost factual recall across
  calibration recipes.
- Calibration may still *modulate* severity: Qwen at 20 %-general lost 16.1 pp on T1 where GLM at
  25 %-code lost 36.8 pp. Two variables differ (ratio and composition) and the base models differ,
  so this is a direction, not an attribution.

**The honest headline is now:** *expert pruning damages closed-book factual recall substantially,
and choosing a broader calibration set does not prevent it.*

## The genuinely new finding: withdraw vs fabricate

Same method, same broad family of calibration, **opposite failure mode**:

| | refusal rate | WRONG rate |
|---|---|---|
| **GLM-REAP 25 %** | 12.7 % → **61.3 %** | — |
| **Qwen-REAP 20 %** | 1.1 % → 11.9 % | 15.8 % → **31.8 %** |

GLM **withdrew** — 54 % of what it lost became "I don't know", which is well-calibrated and safe.
Qwen **fabricates** — refusals stay low while confident wrong answers double.

**Qwen-REAP is the more dangerous artifact of the two**, and it is the one pruned *less*
aggressively with the *better* calibration set. Nothing in a retention benchmark would surface
this; both models would simply score lower.

## Tier profile contradicts the GLM leg

Damage here is **graded by obscurity** — T1 −16.1, T2 −31.2, T3 −42.7, T4 −39.8. On GLM it was
**broad and roughly uniform** (+33–48 pp across T1–T4), which is what falsified P-X1 there.

So the tail-selectivity question is now **open, not settled**: it was falsified on one model and
holds on another. Whatever governs that is not the calibration set, since Qwen's is the broader one.

## Limits

- **K=1, temp 0**, not reproducible on this fleet — existence proof, not rate.
- **Two variables differ from the GLM leg** (ratio 20 vs 25 %, calibration composition) **and so do
  the base models.** No single-variable attribution is available. The Akicou GLM ladder
  (09/19/39/50, one pruner, one base) is what isolates ratio, and it needs ~50 GB of disk `.73`
  does not currently have (13 GB free).
- **One pruner per model.** Nothing separates "REAP as a method" from "these two people's
  application of it."
- **Closed-book only.** Whether Qwen-REAP recovers under retrieval — and whether it shows the C3
  contradiction collapse — is unmeasured. Given it fabricates rather than withdraws, P-Q3's premise
  is gone but the C3 question is *more* interesting here, not less.
- Base-arm verbosity pushes some correct answers into AMBIGUOUS; symmetric across arms, but it
  depresses both absolute numbers relative to a terser model.
