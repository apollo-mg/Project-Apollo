# Phase 1 result — 25% expert pruning multiplies confident factual error ~7×

**Date:** 2026-08-06. **Supersedes the void numbers in `PHASE1_MODE_CONFOUND.md`**, which are retained
there as a retraction. This receipt reports the metric that survives the confound.

## The problem this metric solves

The direct accuracy comparison is unusable in either mode, because the two arms fail to produce a
scoreable answer by *different routes*:

| mode | base | pruned |
|---|---|---|
| thinking OFF | 5 refusals / 160 | **61 refusals / 160** |
| thinking ON | 5 truncations / 160 | **42 truncations / 160** |

Refusal divergence voids the OFF comparison; truncation divergence (3.1% vs 26.3%, **11× the G-5
threshold**) voids the ON comparison. Accuracy over all probes conflates "got it wrong" with "never
committed".

**Error rate among committed answers** — `wrong / (correct + wrong)` — excludes refusals, truncations
and ambiguous responses from **both** numerator and denominator. Divergent refusal or termination
behaviour therefore cannot bias it. It answers a narrower but well-posed question: *when the model
does commit to a factual answer, how often is it wrong?*

## Result — invariant across both modes

T1, 160 matched probe IDs, all four cells:

| cell | correct | wrong | committed | **error rate** |
|---|---|---|---|---|
| base / OFF | 145 | 10 | 155 | **6.5 %** |
| base / ON | 148 | 7 | 155 | **4.5 %** |
| pruned / OFF | 55 | 42 | 97 | **43.3 %** |
| pruned / ON | 73 | 39 | 112 | **34.8 %** |

Both arms improve slightly with reasoning enabled; the gap does not close. **~7× either way.**

## Tier profile — and it falsifies the mechanism

Thinking OFF, K=5, mean [min–max]:

| tier | base | pruned | ratio | Δ pp | committed b/p |
|---|---|---|---|---|---|
| T1 | 5.2 % [5.2–5.2] | 40.0 % [40.0–40.0] | **7.8×** | +34.8 | 194 / 120 |
| T2 | 7.9 % [7.9–7.9] | 55.6 % [54.8–55.9] | **7.1×** | +47.7 | 191 / 93 |
| T3 | 30.1 % [29.3–30.6] | 62.6 % [61.8–62.9] | 2.1× | +32.5 | 134 / 35 |
| T4 | 65.3 % [63.7–68.0] | 100.0 % | 1.5× | +34.7 | 103 / 13 |

**P-X1's mechanism is falsified.** The pre-registered story was that REAP ranks experts by
router-gate × activation-norm over a calibration set, so rare-firing experts are cut first, so **tail**
knowledge should die while common knowledge survives. The prediction was T1 spared (P-R1: within
±2 pp) and T3+T4 hit.

What happened: **T1 and T2 take the worst relative damage.** In absolute terms the damage is roughly
uniform — +33 to +48 pp at every tier. This is broad degradation, not tail-selective deletion.

Read the ratios with care: base error at T4 is already 65.3 %, so the ceiling compresses the ratio
there, and pruned T4 rests on only 13 committed answers (all wrong). Absolute pp is the fairer
cross-tier comparison, and it says *uniform*.

**P-R1: FALSIFIED** — T1 predicted within ±2 pp, observed 5.2 % → 40.0 % error (correct-rate 92.0 % →
36.0 %). Not a near miss; the premise was wrong.
**P-R2: HELD on its face** (T3+T4 accuracy fell far more than 5 pp) **but for the wrong reason** — the
fall is not tail-selective, so the prediction was right by accident. Recorded as such.

## Why this is plausible despite "near-lossless" claims

Cerebras's REAP paper claims near-lossless compression **on code generation**, and their shipped
models are `Qwen3-Coder-REAP-*`. They never claimed factual retention. The unsloth GGUF of this model
has ~21.8k downloads with no widespread reports of it being broken — consistent with a model that is
fine for the coding and agentic work people actually run it for, while being severely degraded on an
axis nobody benchmarks.

That is the campaign's thesis, observed: **the damage is real, large, and invisible to the standard
panel.**

## What this does NOT establish

**The differential claim is untested.** "Knowledge degrades faster than reasoning" requires the
reasoning arm. A ~7× confident-error rate on facts is equally consistent with the model simply being
worse at everything. **HumanEval+ on these same two arms is mandatory before any comparative claim**,
and it has not been run. P-R3 remains NOT RUN.

Other limits:

- **T1 only for the 2×2.** The ON-mode cells were run on T1 (160 probes); T2–T4 have OFF data at K=5
  and no ON data.
- **ON cells are K=1** — existence proof, not a rate (§7). The OFF cells are K=5 with tight ranges.
- One model pair, one prune ratio (64 → 48 experts, 25%), one instrument.
- Committed-error-rate has its own blind spot: it says nothing about a model that refuses everything.
  It must always be reported **alongside** the commit rate, which collapses here — pruned commits on
  120/93/35/13 per tier against base's 194/191/134/103.

## Environment (§9)

Build `b100-0967f4997`, `.73` 2×P100-PCIE-16GB at 1063 MHz / 150 W, `-c 4096 -ngl 99 -sm layer -np 1
--jinja`, temp 0, `max_tokens` 64 (OFF) / 512 (ON), `--exclude-source researcher`, G-1a asserted
`sigmoid` on both arms before every run. Arms: `GLM-4.7-Flash-Q6_K` (29.94 B) and
`GLM-4.7-Flash-REAP-23B-A3B-Q6_K` (23.00 B), both unsloth, G-1 packaging parity verified identical.

## Open

`IKP_T2_0363` returns HTTP 500 from llama-server on the pruned arm in all five runs and never on the
base. Reproducible, input-specific, model-specific. Unrelated to recall; worth isolating.
