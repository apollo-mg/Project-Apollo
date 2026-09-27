# Pre-registration -- quant-abstention CALIB: is the per-file threshold shift one number? (offline, main-campaign data)

**Drafted 2026-09-27, after the main campaign (`RESULT_MAIN.md`) and before any real arm is scored with this analysis.**
The analysis is `analyze_calib.py`, committed together with this file. Only the registered controls (built from the
Q8_0 rows alone) were run before the commit, to test the pipeline; their outcome is recorded below and changed the
claim structure (see Controls). No quantized arm has been run through any part of this analysis.

**Prior art checked:** `ledger_precheck.py "logit bias recalibration abstention threshold per-file offset quant"` ->
receipts found: the main campaign (INDEX L503), the pilot (L502), the AD ladder (L148: calibration moves with bits),
and the effort sweeps (L58, L82). None tests whether the shift is **correctable**. **What this adds:** main showed the
ranking survives and the threshold moves per file; this asks whether one logit bias per file puts the threshold back,
on every question type and without breaking easy items, and whether the shift is shaped like an offset at all.

## Why this is testable offline

`run_main.py` stored the answer-slot top 50 per item with unrounded logprobs and `post_sampling_probs: false`. The top
50 sum to less than 1 on every item checked (C.A: min 0.77, median 0.9996), so they are full-softmax probabilities. A
logit bias `b` added to the three UNKNOWN variants (ids 59322, 21024, 9496) then maps the readout exactly:

    P_abs(b) = P_abs e^b / (1 - P_abs + P_abs e^b)

**Top-50 truncation.** A variant missing from the top 50 has probability at most exp(the 50th logprob). Every analysis
runs twice: on the **lower bound** (P_abs as stored) and the **upper bound** (each missing variant set to that
ceiling). A verdict must hold under both.

This covers the **slot readout only**. Whether generations follow a logit bias is a live question (stage 2, below).

## Data and targets

- All 22 non-ceiling arms of the main campaign, each paired with the Q8_0 run on its own lane (the lanes are
  bit-identical; `RESULT_MAIN.md`, bridge).
- **Labelled set (confirmatory):** the 10 PTQ arms with a direction label in main:
  - timid: AD3XXS, AD3S, UD3XXS, AP2S, APEXM;
  - confident: AD2XS, AP3XXS, APEXN, EXL30, EXL35.
- Everything else (10 unlabelled PTQ arms, Bonsai PTQ1_0 and PQ2_0) is reported with the same verdict, descriptively.
- **Bonsai is not a control.** Its shift is "mixed" (both metrics up), and an offset always moves timidity and
  confabulation in opposite directions, so it fails by arithmetic whatever the criterion is.

## Procedure

1. **Fit.** `b` on a grid [-10, 10], step 0.01, minimising max(|d timidity_H|, |d confabulation_U|) against Q8_0 on the
   fit fold. The verdict bounds each metric separately, so the objective does too. Ties go to the smallest |b|.
2. **Cross-fit.** Stratified 2-fold (template x item arm E/H/U, seed 20260927). Each item is corrected with the `b`
   fitted on the other fold, so no item is scored with a `b` it helped fit.
3. **Verdict "fixed"** (per arm, per bound, on the cross-fitted values):
   - pooled |d timidity_H|, |d confabulation_U| and |d timidity_E| all <= **0.03** (points). The **E guardrail** is
     part of the verdict: a positive `b` that starts refusing capitals the model knows is not a restored Q8_0.
   - The paired t-intervals for d timidity_H and d confabulation_U, at **1 - 0.05/20** (10 arms x 2 metrics), both
     include 0.
   - **Every template cell** (4 templates x {timidity_H, confabulation_U}) has |point| <= **0.10**. This stops a pooled
     `b` from passing by over-correcting operas and under-correcting capitals (main had opera-driven labels: AP2S
     confabulation -0.25 and EXL30 +0.205 on opera). 0.10 is about 2 SE for the noisiest cell and 3 or more for most
     (the per-template SE of the uncorrected paired differences is 0.004-0.055, measured before this prereg on 6 of the
     labelled arms: AD2XS, AD3XXS, UD3XXS, AP2S, EXL30, APEXN; noise only, no correction run), and it
     is well under the opera-only shifts it has to catch.
   - "Fixed both" = fixed under both bounds.
4. **Stability.** 1,000 further random partitions. The fraction whose verdict matches the primary partition's is
   reported, along with the median `b`.
5. **Full-sample `b`** per arm (fit on all 240 items): the number stage 2 would use.

## Confirmatory claims

- **H-fix (practical): one number per file restores Q8_0's operating point.** Supported if >= 7 of the 10 labelled
  arms are fixed under both bounds. Not supported if <= 3. Partial otherwise, reported per arm and per label (timid
  vs confident).
- **H-offset-shape (mechanism): the shift is an offset, not a change of slope.** OLS of the arm's slot logit on Q8_0's
  over H and U items with Q8_0's P_abs in [0.01, 0.99]. The selection is on x only, so it does not bias the slope; it
  drops the extremes, where the truncation bounds and clipping bite. Upper-bound values are used.
  - Per arm: **offset-shaped** if the slope interval at 1 - 0.05/20 lies inside [0.8, 1.25] (|log slope| < log 1.25);
    **slope-changed** if it lies entirely outside; **inconclusive** otherwise.
  - Supported if >= 7 of the 10 labelled arms are offset-shaped; not supported if <= 3; partial otherwise.

**Registered secondary:**
- the same verdict without operas (fit and evaluation on the other 3 templates; main's direction labels leaned on
  operas);
- the fitted `b` per fold;
- before/after per template cell;
- the slope for every arm.

## Controls (built from Q8_0's rows only; run before this commit)

| control | construction | required | outcome |
|---|---|---|---|
| identity | C.B against C.A | `b` = 0.00 in both folds, zero residuals, fixed | **pass** (b 0.00 / 0.00, slope 1.000) |
| positive | C.A's logit + b0, b0 = +1.5 and -1.5 | fixed with `b` = -b0 | **pass** (b -1.50 / -1.50 and +1.50 / +1.50, slope 1.000) |
| slope, timid-like | C.A's logit -> c + a (logit - c), fitted to AD3XXS's pooled shifts (+0.121, -0.112), \|log a\| >= log 1.5 | reported | a = 0.60, c = 2.5, reaching (+0.124, -0.110): **not fixed**, slope 0.600 (slope-changed) |
| slope, confident-like | the same, fitted to AD2XS's (-0.028, +0.213) | reported | a = 0.65, c = -3.9, reaching (-0.030, +0.211): **not fixed**, slope 0.650 (slope-changed) |

**What the controls changed.** The slope synthetics fail "fixed" only narrowly:
- After the best offset, their pooled residuals are 0.025-0.032, and no template cell exceeds 0.052.
- They fail mainly on the interval test, which is exact only because the synthetics carry no noise.

A real noisy arm with a slope change of this size could therefore pass "fixed". So **"fixed" is registered as a
practical claim only: correctable in the mean.** The mechanism claim is carried by the slope readout (H-offset-shape),
which recovers a = 0.600 and 0.650 exactly on the synthetics. Its power on noisy arms is unknown: "inconclusive" is a
possible and honest outcome. No tolerance was changed after the controls ran.

## Stage 2 (live; not part of this registration's run)

If H-fix is supported or partial, the fixed arms' full-sample `b` can be tested on .194 with llama-server
`logit_bias` on the three variant ids:
- **R-slot re-run:** must reproduce the offline prediction. This validates the transform on the real server.
- **R-gen:** the real question. The bias applies at every position, including prose, so generations need not follow
  the slot.

That run needs Mark's go-ahead and .194 powered on, and it gets its own deviation note before it starts.

## Not established by design

- **Practical use needs a reference.** `b` is fitted against Q8_0's readout on these 240 items. A user calibrating
  their own file needs the Q8_0 reference rows (which could ship with the corpus) or labelled items.
- **The fix only covers a prompt that offers an abstain token.** Free-form hedging ("I'm not sure") is not one token,
  and a logit bias cannot reach it.
- **One model, thinking off, one prompt,** as in main.
