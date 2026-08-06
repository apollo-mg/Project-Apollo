# Measurement Insights — what we learned pricing KV codecs

Distilled from our running field guide (`knowledge/measurement-methods.md`), with the
receipts. Everything below was paid for with a wrong conclusion first.

---

## 1. Fidelity ≠ goodness

KLD, hazard, flip-rate, margin all measure *distance from the fp16 model*, not quality.
A codec can beat f16 on a task while having worse hazard (our turbo4 beats q4_0 on PPL yet
loses to it on hazard, depth-driven). Task accuracy is the only goodness court. Say which
one you mean in any verdict.

## 2. The mean is broken for this work. Use the median.

**The anatomy.** A per-layer mean KLD-excess of −2901 μnats decomposed as: top-50 negative
tokens −766 nats, top-50 positive +644 nats, net −285 over 98,280 tokens; signed median
+0.46 μnats; ~71% of tokens moved >100 μnats in BOTH directions. **The mean is a small
residual of two huge canceling tails** — carried by ~0.1% of tokens. That's why it flips
sign across corpus halves, builds, and model quants.

**The reliability table** (split-half Spearman of per-layer rankings, same run, 16 layers,
Qwen3.6-27B; a statistic that can't agree with itself on its own run can't price anything):

| statistic | t8→t4 | t4→t3tcq | t3tcq→t2tcq | t2tcq→t1tcq | fp16→t8 |
|---|---|---|---|---|---|
| excess **mean** | +0.10 | +0.27 | −0.24 | +0.89 | −0.22 |
| excess trim 0.1% | −0.35 | +0.16 | −0.26 | +0.73 | −0.05 |
| excess **trim 1%** | +0.88 | +0.91 | +0.81 | +0.96 | −0.05 |
| excess **median** | **+0.91** | **+0.96** | **+0.92** | **+0.98** | +0.02 |
| **frac tokens > 1e-3** | +0.88 | +0.96 | +0.93 | +0.97 | **+0.98** |

Notes: 0.1% trim is NOT enough — the unstable tail is fatter than that; 1% is the working
level. The mean only becomes usable at very coarse transitions (the ~1-bit rung) where the
signal is enormous.

**Build fragility, quantified.** Re-running 374 identical-config cells after nothing but a
rebuild (one translation unit touched): 152 cells moved ~0.1–0.2% in mean — including pure
fp16→q8-class cells — while medians sat still. Per-layer mean excesses flipped SIGN across
builds (+759μ → −2901μ on the same layer); signed medians stayed ~+0.5μ.
**Never compare means across builds. Same-build ladders are mandatory.**

## 3. median@16k is the validated flip predictor

The question a pricing statistic must answer: does it predict actual decision changes?
Two independent validations:

- **Run level:** median-KLD vs decision flips: **ρ = 0.76**, surviving restriction to
  converged codebooks (0.77). Mean-KLD collapsed with depth: 8k 0.49 → 16k 0.19 →
  32k **−0.16** (sign inverted!) — a convergence confound plus tail noise.
- **Layer level (TRUE argmax flips**, from llama-perplexity's "Same top p" line, 144
  cells): trueflip~median **+0.82** (t8→t4), **+0.84** (t3→t2), **+0.91/+0.93** (t1)
  — vs trueflip~mean **−0.39** at t8→t4. The mean was *anti-correlated* with real flips
  at the fine rung. Hazard-L (KL/(½·margin²)) matched: +0.84…+0.96.

The lenses form two camps: **{median, trim1%, hazard-L, TRUE FLIPS}** vs
**{frac>τ, mean}**. Mechanism: catastrophe tokens are big KL hits on big-margin
(confident) tokens — they don't flip decisions. Flips live where margins are thin and a
broad typical-token elevation crosses them. The median family measures exactly that.

Honest counterweight: frac>τ (catastrophe fraction) replicates too and measures a REAL,
*different* structure — large distortions on confident tokens (compounding/drift
candidate, no flip today) — and it is the ONLY lens that resolves the finest (fp16→q8)
transitions. We carry it in every table next to the median; we just don't price on it
alone. On a NEW model, pick the lens with the best split-half reliability **on that
model** — on one of our three models frac was the most reliable and the median-built
schedule wasn't the winner. The mean was never best anywhere.

### The depth-dilution artifact — why deep KLD "improves"

Found while Spearman-ing per-depth KLD (2k/8k/16k/32k) against flips, per-position dumps
in hand. Teacher-forced mean KLD *goes down* as context gets longer — and it is an
artifact, not the codec getting better with depth:

- The mean is set by sparse catastrophic spikes (>1 nat), and the fraction of spike
  tokens **falls with depth: 2.3% @2k → 0.96% @32k** (early bands @32k ≈ 0%). More
  context = more-constrained predictions = ever more teacher-forced-easy filler tokens
  ("the", "and", boilerplate) crowding the average, while the per-token median sits flat
  (~0.0018) in every position band at every depth. Deep windows don't hurt less — they
  just contain proportionally more tokens that were never at risk.
- Consequence for depth choice: mean-KLD's flip-prediction by depth read 2k +0.28 /
  8k +0.49 / 16k +0.48 / 32k +0.15 — "8k looks best" — but restricted to converged
  (deployable-quality) codebooks it collapsed to 0.19 @8k and **−0.16 @32k** (sign
  inverted). The apparent depth structure was convergence-confound + dilution. Median@16k
  survived the same restriction (+0.76 → +0.766).
- The literature has the same physics under averaged PPL: **LongPPL** (arXiv 2410.23771)
  shows ~90% of long-context tokens are "context-agnostic," making averaged PPL correlate
  ~0 with downstream while key-token loss correlates −0.96. (At *coarse* scale mean-KLD
  still tracks flips fine — "Accuracy is Not All You Need" reports ρ=0.981 across model
  pairs; the failure is *fine discrimination* among similar-quality candidates, which is
  exactly the pricing/selection regime.)
- **Warning: last-k does NOT rescue the teacher-forced mean.** The last-64 zone is the
  *lowest*-KLD region (0.09–0.35× the full-window mean) — recency = most context = most
  constrained — even though those queries attend over the most-quantized cache. So
  neither full-window nor last-k teacher-forced KLD can see autoregressive compounding;
  only autoregressive judges (trajectory-survival, live-cache generation, task runs) can.
  This coexists with §l64 below: l64 is the right lens for *comparing codecs/schedules
  at the decode frontier* (relative), but its absolute level is low and it still can't
  price compounding.

## 4. The "codebook lottery" that dissolved into a statistic

Template for instrument-vs-phenomenon investigations. June sweeps (3 pools × 100 Lloyd
iterations, each codebook measured in-model at 4 depths) read under MEAN-KLD looked like a
lottery: quality non-monotone in training iteration (iter15 "beating" converged iter60),
within-family MSE↔KLD Spearman ≈ 0, seed reorderings. Verdict at the time: "codebook
selection is a lottery; MSE mis-selects."

Re-reading the SAME archives — no new runs — under both labels, ρ(statistic, Lloyd iter):

| pool | median@16k | mean@16k (same runs) |
|---|---|---|
| pool A | **−0.66** | −0.29 |
| pool B | **−0.92** | +0.09 |
| pool C | **−0.72** | −0.19 |

(Lower KLD = better, so negative ρ = training monotonically improves quality.) Training
improves the robust label essentially monotonically in all three pools; the mean label is
noise on identical data. Under median labels, train-MSE became predictive of KLD again
(ρ ≈ +0.66) — the trainer was never broken either. **A "lottery" among objects is a
hypothesis about the JUDGE before it is a fact about the objects.**

## 5. l64 — score where the model actually decodes

`l64` (a.k.a. lastk64) = KLD over only the **last 64 positions** of each window — the true
decode frontier — instead of the whole scored half. Fork hook: `TURBO_SCORE_LAST_K=64`.

**Why it exists — the experiment that forced it:** we tested protecting the *tail end of
KV rows* (the most recent positions) at high precision — a "bathtub" allocation: fp16 on
the attention-sink positions [0,128) + the recent tail, cheap tier in the middle basin —
against a control ("naivepos") holding the SAME byte multiset but spread evenly across
depth. Matched 0.483 bytes/value, ctx 8192, both scored both ways:

| config | B/val | full-window KLD | lastk64 KLD |
|---|---|---|---|
| flat t4 (baseline) | 0.516 | 0.0254 | 0.0219 |
| **bathtub** (sink+recent protected) | 0.483 | 0.0540 | **0.0232** |
| naivepos (same bytes, spread) | 0.483 | 0.0578 | 0.0516 |

Under full-window scoring, bathtub vs naivepos is **+6.6% — invisible (~1.5σ)** — and
bathtub even "loses" 2.1× to the flat baseline. Under l64, bathtub beats naivepos by
**55% (a 2.2× KLD win)** and ties the flat baseline with **6.4% fewer bytes**. Full-window
scoring grades positions the model never decodes from in production, so it structurally
cannot see position-targeted protection; the recency benefit only exists at the frontier.
**Any positional/recency/VBR scheme evaluated on full-window KLD alone will be judged
wrong — score at the decode positions.**

(Same lesson from the other direction: the recency wall is soft and wide — protecting the
last <64 positions buys nothing; the knee is at ~128–512 recent positions, ~512 captures
~80% of the recoverable damage.)

l64 is also our preferred *codebook selection* lens (with a 32k confirm): full-window KLD
can stay flat while the frontier rots, because deep positions are dominated by
context-agnostic tokens (the same dilution mechanism as §3's depth artifact). Keep the two
findings straight: l64 fixes *where you score* (relative comparisons at the frontier);
it does not fix teacher-forcing itself — compounding damage still needs an autoregressive
judge.

## 6. Practical rules (the checklist)

1. **Coherence gate first.** Generate a paragraph and read it before trusting any metric —
   numerically-dead paths can score as "mild degradation" (we had a broken kernel show
   batch-1 PPL 15.6 vs 4.6 while batched metrics looked fine).
2. **Anchor must be exactly zero/clean** (f16-vs-f16) before reading any cell.
3. **Paired anchors, per-token dumps.** Every cell vs a same-config hi-tier anchor;
   per-token diff; the harness floor differences out. Difference-of-medians ≠
   median-of-differences — printed per-run stats are triage, conclusions come from paired
   dumps.
4. **Split-half reliability gate:** even/odd + first/second-half chunks, Spearman the two
   half-rankings; publish orders only at ρ ≥ ~0.8. This is what killed the mean.
5. **Same-build ladders.** Any cross-object comparison must be one build; anchor cells
   (an unchanged rung) ride in every campaign — if the anchor moves, stop, the instrument
   is broken.
6. **Every judge has a seed floor.** Two quality-equal implementations of the SAME math
   score ~1.1% mutual flips, mean-KLD ≈ the codec's own scale. Calibrate the floor once
   with a quality-equal pair; deltas under ~2× floor are unreadable; unpaired fine-tier
   comparisons measure the noise realization, not quality.
7. **Depth is part of the metric.** Statistics that agree at 2k can invert by 32k
   (mean-KLD's flip-prediction went 0.49 → −0.16). Validate at deployment depth.
