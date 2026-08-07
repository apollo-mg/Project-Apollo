# Result — the contradiction collapse tracks PRIOR STRENGTH, not pruning as such. A gate failed.

**Date:** 2026-08-07. `0xSero/Qwen3.6-28B-REAP20-A3B` vs `Qwen/Qwen3.6-35B-A3B`, both mradermacher
Q6_K, `.73` 2×P100 @ 1063 MHz / 150 W, build `tom_default`, `-c 4096 -ngl 99 -sm layer -np 1
--jinja`, thinking OFF, temp 0, K=1. Probes built by `build_c3_probes.py` / `build_rag_probes.py`
**unmodified** from the GLM legs. Pre-registered in `PREREG_QWEN_CONTEXT.md` (commit `2237f33`),
scored by `qctx_analyze.py`. 461 probes per arm, **0 errored, 0 truncated on both arms.**

`n_expert` asserted from the runtime's own `print_info` before each arm: pruned 205, base 256.

## Prediction scoring (§8)

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-QX0** | GATE — pruned C1 ≥ 90 % | 0.80 | **HELD**, 100.0 % (199/199) |
| **P-QX1** | GATE — base C3 order sensitivity ≤ 20 pp | 0.75 | **FALSIFIED**, 50.8 pp |
| **P-QX2** | HINGE — pruned C3 order sensitivity ≥ 30 pp | 0.55 | **NOT SCORED** — gate failed |

The pruned arm's order sensitivity is **62.7 pp**, which would have cleared the P-QX2 threshold. It is
not claimed, because the pre-registration made P-QX1 a gate precisely so that an arm gap could be
attributed. The base arm does 50.8 pp of the same thing. **Scoring P-QX2 HELD here would be reading
the number I wanted out of an instrument that just failed its control.**

## The raw cells

| arm | cond | n | corr | wrong | refus | raw | committed |
|---|---|---|---|---|---|---|---|
| base | C1 | 199 | 199 | 0 | 0 | 100.0 % | 100.0 % |
| base | C3a gold-1st | 131 | 128 | 3 | 0 | 97.7 % | **97.7 %** |
| base | C3b gold-2nd | 131 | 61 | 69 | 1 | 46.6 % | **46.9 %** |
| pruned | C1 | 199 | 199 | 0 | 0 | 100.0 % | 100.0 % |
| pruned | C3a gold-1st | 131 | 126 | 2 | 3 | 96.2 % | **98.4 %** |
| pruned | C3b gold-2nd | 131 | 44 | 79 | 8 | 33.6 % | **35.8 %** |

```
ORDER SENSITIVITY    base 50.8 pp    pruned 62.7 pp        [GLM was: base 6.6 pp, pruned 59.1 pp]
```

**P-QX0 passed its gate.** Both arms answer 199/199 on uncontested single-entry context, zero
refusals, zero AMBIGUOUS — so retrieval rescue now holds on 2 models / 2 pruners / 2 ratios /
2 opposite failure modes. **Stated as a gate, not a headline:** 100 % on *both* arms is a ceiling
with no demonstrated power to discriminate, the same limitation already recorded against C2 in
`CAMPAIGN_SYNTHESIS.md`. It licenses reading C3; it does not by itself evidence that pruned models
are good at retrieval, because nothing here could have shown otherwise.

Qwen3.6's verbosity — which cost 2.0/3.4 % to AMBIGUOUS on the closed-book leg — vanishes entirely
when the answer is supplied; the lenient and strict tallies are identical in every cell.

## What the design actually asks

The prompt is worth quoting, because it changes the reading:

```
Reference material:
- In what year was the Visigothic sack of Rome?  410
- In what year was the Visigothic sack of Rome?  541

Using only the reference material above, answer:
In what year was the Visigothic sack of Rome?
```

Both entries are *in* the reference. **The reference alone cannot adjudicate.** The instruction says
"using only the reference material", so the only route to a correct answer is to override that
instruction with the parametric prior. C3 is therefore not "does context beat prior" — it is
**"is the prior strong enough to overrule a self-contradictory context."**

## Why the gate failed: prior strength, not pruning

Committed gold rate on the gold-2nd cell, by tier, both campaigns:

| | T1 | T2 | T3 | T4 | ALL |
|---|---|---|---|---|---|
| **GLM base** | 100.0 % (26) | 92.9 % (28) | 71.4 % (7) | — | **93.4 %** |
| **GLM pruned** | 38.1 % (21) | 31.0 % (29) | 33.3 % (9) | — | **33.9 %** |
| **Qwen base** | 85.7 % (14) | 83.8 % (37) | 22.0 % (41) | 23.7 % (38) | **46.9 %** |
| **Qwen pruned** | 92.3 % (13) | 63.6 % (33) | 15.0 % (40) | 13.5 % (37) | **35.8 %** |

**Contradiction robustness is a function of how well the model knows the fact.** Qwen base holds at
T1/T2 (85.7 / 83.8 %) and floors at T3/T4 (22.0 / 23.7 %). It is not position-following in general;
it is position-following *exactly where its prior is weak.*

### The population-selection confound — a design error, named

The C3 population is "base got it right, pruned got it wrong." That set inherits the tier profile of
whatever the pruning damaged:

| | T1 | T2 | T3 | T4 | obscure share |
|---|---|---|---|---|---|
| **GLM C3 mix** (n=68) | 38 % | 46 % | 15 % | 1 % | **16 %** |
| **Qwen C3 mix** (n=131) | 11 % | 28 % | 31 % | 30 % | **61 %** |

GLM's damage was broad and roughly uniform, so its C3 set is 84 % well-known. Qwen's damage is
graded by obscurity, so its C3 set is 61 % obscure — *by construction*. Much of the 6.6 → 50.8 pp
base difference is this, not a model property.

**But not all of it.** At every matched tier Qwen base is still worse than GLM base (T1 85.7 vs
100.0, T2 83.8 vs 92.9, T3 22.0 vs 71.4). The T3 comparison is the largest and the weakest — GLM
contributes **n=7** there and cannot carry that claim. Recorded as a direction, not an attribution.

**The GLM result survives this re-analysis at T1/T2, and is untested at T3/T4.** GLM base held and
GLM pruned collapsed at every tier GLM actually populates (base 100.0 / 92.9 / 71.4, pruned
38.1 / 31.0 / 33.3), so the contrast is not a composition artifact in the well-known band.

But the prior-strength mechanism makes its prediction in the **obscure** band, and GLM has almost no
obscure band — T3 n=7, T4 n=1. GLM therefore confirms the mechanism only where both models already
agree. **The gradient that carries the mechanism is Qwen's alone.** A GLM C3 set stratified to
include T3/T4 is the experiment that would test it on a second model; it has not been run.

## The pruning effect, tier-matched

With the base arm as its own control per tier, what pruning costs Qwen on contradicted retrieval:

| tier | base → pruned | Δ |
|---|---|---|
| T1 | 85.7 % → 92.3 % | +6.6 pp (n=13/14 — noise) |
| T2 | 83.8 % → 63.6 % | **−20.2 pp** |
| T3 | 22.0 % → 15.0 % | −7.0 pp (base already at floor) |
| T4 | 23.7 % → 13.5 % | −10.2 pp (base already at floor) |
| ALL | 46.9 % → 35.8 % | **−11.1 pp** |

The damage is **concentrated at T2** — the band where the base prior is strong enough to adjudicate
and pruning is strong enough to break it. T1 is untouched, T3/T4 have no headroom left. This is the
same tier signature as Qwen's closed-book damage, which is the unifying observation of this leg.

## Paired structure — the effect is unidirectional

Each of the 131 stems appears in both orders. Counting per stem:

| gold picked in… | base | pruned |
|---|---|---|
| both orders | 61 | 44 |
| only when gold 1st | 67 | 82 |
| **only when gold 2nd** | **0** | **0** |
| neither | 3 | 5 |

**Zero exceptions in 262 pairs.** The gold-2nd-correct set is a strict subset of the gold-1st-correct
set in both arms. A noisy effect would produce flips in both directions; this produces none. The
position effect is real, ordered, and not a sampling artifact.

**Cross-arm nesting is NOT clean, and the −11.1 pp should be read accordingly.** Asking the same
question across arms rather than across orders — of the 61 stems base gets right on C3b, are
pruned's 44 a subset?

| C3b | lost (base ✓, pruned ✗) | gained (pruned ✓, base ✗) | net |
|---|---|---|---|
| stems | **20** | **3** | −17 |

Not monotone degradation: 23 stems change state, 87 % of them in the losing direction. The net
−11.1 pp understates gross movement by about a quarter. (C3a, for contrast, moves 3 lost / 1 gained
— nearly static, as its 97.7 → 98.4 % marginal implies.)

## Gates and bounds

- **G-5 termination:** `no_answer` **0.0 % on both arms, all conditions.** Cannot be tripped.
- **Refusal spread on C3b** — base 0.8 %, pruned 6.1 % (5.3 pp), and `committed` excludes refusals,
  so it is bounded rather than waved through: crediting **all 8** pruned refusals as gold and only
  base's 1 gives pruned 39.7 % vs base 47.3 % — still −7.6 pp. Booking them all WRONG gives
  33.6 % vs 46.6 %. **The direction survives either extreme.**
- **Instrument validity:** 100 % of committed-WRONG responses (base 72/72, pruned 81/81) are text
  that appeared in the supplied context. The models are selecting the planted entry, not emitting an
  unrelated third answer.
- **AMBIGUOUS:** 0 in every cell of both arms.
- **Pair symmetry:** C3a and C3b are the same 131 stems with entry order swapped and nothing else —
  asserted programmatically, not by inspection.

## What this does to the campaign

`CAMPAIGN_SYNTHESIS.md` §6 says *"the pruned model largely picks whatever comes first."* That stands
for GLM and **does not generalize as stated.** The corrected claim:

> Contradiction robustness is a function of prior strength. A model overrules a contradictory
> retrieved entry when it knows the fact well, and follows position when it does not. Pruning
> degrades this **by weakening the prior**, so the tier profile of the contradiction defect follows
> the tier profile of the closed-book damage in that model. In GLM — damaged uniformly — the
> collapse is uniform and large (**−59.5 pp arm gap** on the gold-2nd cell, 93.4 → 33.9 % — distinct
> from GLM's **59.1 pp order sensitivity**, which is a within-arm quantity; the two are adjacent in
> value and easily conflated). In Qwen — damaged by obscurity — it is −20.2 pp at T2 and absent
> where the base had no headroom.

This mechanism covers *magnitude* across both models with one variable and predicts the tier
signature in each. **It does not subsume the other C3-family results, and does not claim to.**
Prior strength says nothing about why GLM's collapse depends on *whose* wrong answer competes
(own confabulation 33.9 % vs foreign gold 83.9 %, `RESULT_C4_C5.md`), nor about tag-following
(C4b 44.6 %). Those need a second variable — plausibly that a foreign wrong answer is rejectable on
*relevance* grounds the model's own confabulation is not. Two mechanisms, not one: prior strength
governs how hard the model fights, own-vs-foreign governs whether the competing entry is a
contender at all. Both are open.

**The incidental finding is the more practically alarming one — with two caveats it must carry.**
Base `Qwen3.6-35B-A3B`, unpruned, un-quantized beyond Q6_K, fails to reproduce a fact it answered
correctly closed-book in **53 % of these pairs** when a contradicting entry is placed first — 78 %
on T3/T4.

1. **The two entries are degenerate duplicates** — identical question stems differing only in the
   answer value. No differing phrasing, source, or surrounding context, so position is the *only*
   residual signal. This structurally **maximizes** the position effect and is not what a real
   retriever returns. Read it as an upper bound on the phenomenon, not an estimate of it.
2. **"Answers correctly closed-book" is a single K=1 sample** on a fleet with documented temp-0
   bistability (`DETERMINISM_TEMP0_GLM_P100.md`). The precise claim is *"abandons a fact it got
   right once."*

Neither caveat removes the effect — 78 % on T3/T4 is far outside anything K=1 noise produces across
79 items — but any public statement of this number must carry both.

## Limits

- **K=1, temp 0**, not reproducible on this fleet (`DETERMINISM_TEMP0_GLM_P100.md`). Existence
  proof, not rate.
- **The population-selection confound above is a defect of this design, not a finding.** Comparing
  contradiction robustness across models requires a **tier-matched or stratified** C3 population.
  Neither GLM's nor Qwen's set was built that way. A clean cross-model claim needs a re-run.
- **GLM's obscure-tier n is 7.** Every GLM T3/T4 statement here is underpowered.
- **Two variables differ between the model pairs** (ratio 20 vs 25 %, calibration composition) plus
  the base models themselves. No single-variable attribution.
- **One pruner per model.** Nothing separates REAP-the-method from these two applications of it.
- The C3 prompt instructs "using only the reference material", so a correct answer requires
  *disobeying* the instruction. A model that follows instructions more literally will score worse
  without being less capable. Constant across arms; not constant across model families.
