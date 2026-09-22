# Result — the noise floor is 10.3%, identical to the signal. Every quant comparison is void.

**2026-09-22 09:56-11:25, `.194`.** Prereg `PREREG_NOISE_FLOOR.md`, committed before the run.
**Both arms are `Qwen3.8-27B-Q6_K`, the same file** — arm A on GPUs {0,1}, arm B on {2,3},
identical flags, identical corpus (`families_v4.json`), fixed scorer, `TZ` pinned, 40 items,
1 rep. **The only difference between the arms is the sampling draw.**
Raw: `noise/noise_{A,B}_q6k_20260922.jsonl`.

## The number

```
scorable 29    both pass 22    b=2    c=1    both fail 4
NOISE FLOOR = 3/29 = 10.3%
arm A 82.8%    arm B 79.3%     (the same model)
```

## Against the run it was built to interpret

| run | models | discordance | b : c | arm A | arm B |
|---|---|---:|---:|---:|---:|
| **noise floor** | **Q6_K vs Q6_K** | **3/29 = 10.3 %** | 2:1 | 82.8 % | 79.3 % |
| v4 re-run | Q6_K vs AD-IQ3_S | **3/29 = 10.3 %** | 1:2 | 72.4 % | 75.9 % |

**Identical. Same numerator, same denominator, same rate.** Two runs of the *same model* disagree
exactly as often as a Q6_K disagrees with a 3.5 bpw quant. Both splits are near-symmetric, which
is what pure sampling produces and what a real effect does not.

**The aggregate pass rate is no better.** Three arms of the identical `Qwen3.8-27B-Q6_K` file,
same config, same corpus:

```
v4 re-run arm A   72.4%
noise    arm A    82.8%
noise    arm B    79.3%
spread            10.4 points
```

## Consequence: every quant comparison this campaign has produced is void

Not "weak", not "underpowered" — **void**. 13.9 %, 12.1 %, 22.2 %, 27.6 %, 10.3 % were all
measured at or below a noise floor of 10.3 %, with one rep at temperature 1.0. None of them
demonstrated that two models differ. `RESULT_PILOT_V4_RERUN.md` withdrew two claims on scorer
grounds; this withdraws the remaining measurement grounds under all of them.

The instrument has **no demonstrated discriminating power** in its current configuration. That is
a property of the configuration — one rep, temp 1.0 — not of the corpus construction, which the
fixture work validated independently.

## Predictions, scored

| id | prediction | result |
|---|---|---|
| **P-N1** | noise floor **below** 10.3 % | **FALSIFIED** — exactly 10.3 %, to the item |
| P-N2 | noise floor > 0 | **CONFIRMED** — 3 discordant pairs |
| P-N3 | arm pass rates within 10 pp | **CONFIRMED** — 3.5 pp |
| **P-N4** | `WRONG-INACTION` stays 0 on both | **FALSIFIED** — arm A had 1 |
| P-N5 | gate rungs pass | **CONFIRMED** — A 8/9, B 9/9 |

P-N1 was committed at 0.55, which was the honest position and still lost. P-N4's falsification is
small but real: over-caution does occur, just rarely.

## What this does and does not damn

**Not the corpus.** `families_v4` verifies 40/40 against the world, 0 path-dependent clauses, and
its rung structure behaved as designed. The items are sound; the *sampling regime* cannot resolve
differences between them.

**Not the scorer.** The three fixes stand and are what made this measurement trustworthy enough
to act on.

**It does damn single-rep temp-1.0 comparison**, which is every comparison run so far.

## What would fix it, given card sampling is non-negotiable

Temp 0 is ruled out by decision — manufacturer sampling is the point, and
`[[thinking-off-in-harnesses]]`-style deviations are how the Ornith arm died. So:

1. **Reps, compared as rates.** Per-item pass *rate* over N reps, not a majority vote —
   `RESULT_A1_SIZING_DISCORDANCE` measured that majority voting *suppresses* discordance
   (12.5 % -> 0 %). Noise falls as 1/sqrt(N); the real effect does not.
2. **More items.** Symmetric noise inflates both `b` and `c`, pushing psi toward 0.5, and psi is
   the expensive term in A1's table (0.80 -> 20 pairs, 0.60 -> 194). More items buy back what
   noise dilutes.
3. **Both**, which is what the sizing must now be computed from — and cannot be, until the real
   effect size is known, which needs a run that can see it.

**The honest status: the campaign does not yet have an instrument that can measure what it was
built to measure.** That is a better place than believing it does.

## What this does NOT establish

- **One noise-floor sample.** 3 discordant pairs is itself a noisy estimate of noise; the true
  floor could be materially higher or lower. A second identical pair would tighten it.
- **Socket and GPU pair are confounded with arm**, as the prereg declared. `splitscale` measured
  the pairs equivalent (13.00 vs 13.03 t/s), but this run cannot separate hardware from sampling.
- **Nothing about whether Q6_K and IQ3_S actually differ.** They may differ substantially; this
  says only that this instrument, so configured, cannot tell.
- **No rep count is derived here.** Establishing one needs a real effect size to size against.
