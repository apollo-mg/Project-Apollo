# Result -- quant-abstention CALIB: one logit bias per file restores Q8_0's "I don't know" for half the shifted files; the shift is not generally an offset

> **Scope, added 2026-09-27.** Everything here is about the **forced answer slot**, where the model answers with no
> text written first. That is the setting of log-prob confidence scoring and single-token answers. In the model's own
> generations the confident files do not over-answer (`RESULT_MAIN.md`, Correction), so a slot-fitted bias applied
> to generation would over-correct them. Stage 2 (live `logit_bias` generations) was **not run** for that reason;
> the in-context readout (`PREREG_INCTX.md`) replaced it.

**2026-09-27.** Pre-registration: `PREREG_CALIB.md` (commit 9bd05f4, written and committed before any quantized arm was
scored). Analysis: `analyze_calib.py`. Output: `RESULT_calib.json` (arms), `RESULT_calib_CONTROLS.json` (controls).
Data: the main campaign's stored answer-slot top 50 (`raw/main_*.jsonl`); nothing was re-run. **Offline, slot readout
only.** Whether generations follow the bias is stage 2, not run.

## Verdicts (as registered)

| claim | rule | result |
|---|---|---|
| **H-fix** (one number restores Q8_0's operating point: pooled timidity, confabulation and easy-item timidity within 0.03, intervals include 0, every template cell within 0.10) | >= 7 of the 10 labelled arms supported, <= 3 not | **partial: 5 of 10** (AD2XS, AD3S, UD3XXS, APEXM, EXL35) |
| **H-offset-shape** (the shift is an offset: slope of the arm's slot logit on Q8_0's inside [0.8, 1.25]) | >= 7 of 10 supported, <= 3 not | **not supported: 3 of 10** (APEXM, EXL30, EXL35) |

**Controls** (from Q8_0's rows only; `PREREG_CALIB.md`):
- The identity (C.B vs C.A) fits b = 0.00 with zero residuals.
- Synthetic offsets of +/-1.5 are recovered exactly.
- Synthetic slope changes (0.60, 0.65) fail "fixed" and read as slope-changed.
- The truncation bounds never decide a verdict: lower and upper bound agree on every arm.

## Per arm (upper bound; cross-fitted; labelled arms in bold)

`b` is the full-sample logit bias on the three UNKNOWN variants: negative for timid files, positive for confident ones.
"Before" is the arm minus Q8_0. "After" is the cross-fitted residual. The worst cell is the largest template-level
residual.

| arm | main label | scored bpw | b (full) | before tim / con | after tim / con / E | worst cell | fixed | w/o opera | stability | slope [99.75 %] | shape |
|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| **AD2XS** | confident | 2.85 | +1.31 | -0.028 / +0.213 | +0.026 / +0.026 / +0.010 | opera con -0.084 | **yes** | no | 0.94 | 0.70 [0.57, 0.82] | inconclusive |
| **AD3XXS** | timid | 3.50 | -1.15 | +0.121 / -0.112 | +0.034 / +0.033 / +0.005 | capital tim +0.094 | no | no | 1.00 | 0.64 [0.56, 0.71] | slope-changed |
| **AD3S** | timid | 3.77 | -1.38 | +0.106 / -0.133 | +0.010 / +0.009 / +0.003 | opera con +0.088 | **yes** | yes | 1.00 | 0.79 [0.71, 0.88] | inconclusive |
| **UD3XXS** | timid | 3.48 | -1.78 | +0.155 / -0.144 | +0.014 / +0.014 / +0.003 | opera con +0.058 | **yes** | yes | 1.00 | 0.92 [0.80, 1.05] | inconclusive |
| **AP2S** | timid | 2.75 | -1.08 | +0.165 / -0.074 | +0.076 / +0.077 / +0.019 | capital tim +0.218 | no | no | 1.00 | 0.55 [0.41, 0.69] | slope-changed |
| **APEXM** | timid | 4.01 | -0.72 | +0.037 / -0.073 | -0.000 / -0.002 / +0.001 | opera con +0.066 | **yes** | yes | 1.00 | 0.92 [0.81, 1.02] | offset-shaped |
| **AP3XXS** | confident | 3.09 | +0.37 | +0.017 / +0.076 | +0.033 / +0.035 / -0.000 | novel con +0.224 | no | no | 1.00 | 0.79 [0.64, 0.93] | inconclusive |
| **APEXN** | confident | 3.21 | +0.63 | -0.000 / +0.113 | +0.030 / +0.033 / +0.005 | novel con +0.236 | no | no | 1.00 | 0.63 [0.49, 0.76] | slope-changed |
| **EXL30** | confident | 4.05 | +0.38 | +0.008 / +0.061 | +0.024 / +0.024 / -0.000 | opera con +0.146 | no | yes | 1.00 | 1.01 [0.90, 1.12] | offset-shaped |
| **EXL35** | confident | 4.50 | +0.40 | -0.000 / +0.054 | +0.014 / +0.013 / +0.000 | novel con +0.073 | **yes** | yes | 1.00 | 1.00 [0.91, 1.09] | offset-shaped |
| UDQ2KXL | none | 2.82 | +0.20 | +0.032 / +0.074 | +0.046 / +0.043 / +0.012 | capital con +0.146 | no | no | 1.00 | 0.54 [0.40, 0.69] | slope-changed |
| UD2M | none | 3.00 | -0.26 | +0.065 / +0.015 | +0.048 / +0.048 / +0.003 | novel con +0.210 | no | no | 1.00 | 0.72 [0.57, 0.86] | inconclusive |
| UD4XS | none | 4.13 | -0.38 | +0.024 / -0.031 | +0.008 / +0.008 / +0.000 | capital tim +0.025 | **yes** | yes | 1.00 | 0.98 [0.91, 1.04] | offset-shaped |
| GSQ2XS | none | 2.50 | -1.42 | +0.223 / -0.085 | +0.100 / +0.094 / +0.010 | novel con +0.362 | no | no | 1.00 | 0.46 [0.28, 0.65] | slope-changed |
| GSQ2S | none | 2.75 | +0.10 | +0.036 / +0.056 | +0.042 / +0.043 / +0.010 | novel con +0.157 | no | no | 1.00 | 0.66 [0.53, 0.79] | slope-changed |
| GSQ3XXS | none | 3.00 | -0.55 | +0.105 / -0.005 | +0.062 / +0.062 / +0.005 | capital tim +0.199 | no | no | 1.00 | 0.68 [0.53, 0.83] | inconclusive |
| GSQ3S | none | 3.50 | +0.05 | +0.013 / +0.021 | +0.015 / +0.015 / +0.000 | novel con +0.082 | **yes** | yes | 1.00 | 0.89 [0.75, 1.03] | inconclusive |
| AP3XS | none | 3.31 | +0.06 | +0.017 / +0.027 | +0.022 / +0.020 / +0.003 | novel con +0.124 | no | no | 1.00 | 0.77 [0.66, 0.88] | inconclusive |
| AP3S | none | 3.47 | -0.63 | +0.062 / -0.050 | +0.022 / +0.022 / +0.005 | novel con +0.125 | no | no | 1.00 | 0.75 [0.64, 0.86] | inconclusive |
| EXL25 | none | 3.59 | -0.59 | +0.037 / -0.045 | +0.010 / +0.009 / +0.001 | opera con +0.133 | no | yes | 1.00 | 1.01 [0.85, 1.17] | offset-shaped |
| BON1 | mixed | 1.76 | +0.05 | +0.066 / +0.076 | +0.074 / +0.071 / +0.009 | university con +0.301 | no | no | 1.00 | 0.51 [0.33, 0.70] | slope-changed |
| BON2 | mixed | 2.14 | +0.05 | +0.066 / +0.077 | +0.074 / +0.071 / +0.009 | university con +0.301 | no | no | 1.00 | 0.51 [0.33, 0.70] | slope-changed |

## What it says

1. **Half the shifted files are fixed by one number.** AD3S, UD3XXS, APEXM and EXL35 land within 0.015 of Q8_0 on
   timidity and confabulation, with easy items untouched (<= 0.003) and no template off by more than 0.09. The fitted
   `b` is stable across partitions (the two folds agree within 0.2), so this is a property of the file, not the draw.
   Two unlabelled files pass too: UD4XS and GSQ3S.
2. **AD2XS, the example in the summary, is a marginal pass.**
   - b = +1.31 brings confabulation from +0.213 to +0.026 while holding easy items.
   - It passes partly by cancellation: operas are over-corrected (-0.084) while capitals, novels and universities stay
     at +0.04 to +0.07.
   - Without operas it fails (0.037 / 0.041 > 0.03).
   - Its verdict flips in 6 % of partitions; every other arm's verdict is stable at 1.00.
3. **The failures fall into two kinds:**
   - **Near-misses on the pooled bound:** AD3XXS (0.034 / 0.033), AP3XXS (0.033 / 0.035), APEXN (0.030 / 0.033).
     AP3XXS and APEXN also fail on one template: novels, confabulation +0.22 to +0.24.
   - **Opera-driven:** EXL30's only failing cell is opera confabulation (+0.146). Without operas it is fixed with
     b ~ 0; its "confident" label in main came from operas, the template where generations cannot cross-check the
     readout. EXL25 is the same pattern (unlabelled).
   - **Clearly unfixable:** AP2S (residual +0.08 on both metrics, capitals +0.22), GSQ2XS (+0.10), and both Bonsai
     packings (+0.07; "mixed" in main, so an offset cannot help by arithmetic).
4. **After the best offset, a residual is left, and it is the same size on both metrics.** "After" timidity and
   confabulation come out nearly equal and positive for almost every file (for example AP2S +0.076 / +0.077, UD2M
   +0.048 / +0.048). The minimax fit balances them, so the common value is the part of the file's miscalibration that
   no threshold can remove: the file is worse than Q8_0 at *both* refusing and answering, by that much. It is 0.015 or
   less for the fixed files and EXL25, and 0.04-0.10 for the 2.5-3.0 bpw GSQ and UD files, AP2S and Bonsai.
5. **The shift is mostly not an offset.**
   - Every non-EXL3 file below 3.35 scored bpw has a slope of 0.46-0.79 (10 of 10).
   - Above that size it is mixed (0.64-0.98).
   - The EXL3 files sit at 1.00-1.01, but all three are above 3.5 scored bpw, so size and method are confounded there.
   - The fixed files tend to have the higher slopes (0.70-1.00).

   What a slope below 1 means (the quant's logits compressed, or weaker item-level agreement with Q8_0) is open; see
   Exploratory, below.

## Exploratory (after the registered result was committed; `explore_calib.py`, `EXPLORE_calib.json`)

Nothing here changes a registered verdict or label.

**1. Where top-50 censoring is small, a slope below 1 is compression, not only weaker agreement.** Over the same items as the slope readout,
slope = r x SD ratio, where the SD ratio is the arm's logit SD over Q8_0's. Independent item noise can only raise the
SD ratio, so a ratio below 1 is conservative evidence that the arm's slot logits are **compressed**. The
UNKNOWN-vs-answer odds are pulled toward indecision, like a temperature on that one choice.

| pattern | files (SD ratio, r; arm-side censored items) |
|---|---|
| **compressed**, little censoring (<= 3 items) | AD3XXS (0.69, 0.92; 2), AP2S (0.73, 0.76; 1), GSQ2XS (0.78, 0.59; 2), Bonsai (0.82, 0.63; 3), AP3S (0.84, 0.89; 0), AD3S (0.85, 0.93; 0), UD2M (0.87, 0.82; 0) |
| compressed or floored, **unresolved** (6-43 items) | UDQ2KXL (0.74, 0.74; 43), APEXN (0.79, 0.80; 8), GSQ2S (0.80, 0.83; 15), AD2XS (0.83, 0.84; 13), GSQ3XXS (0.86, 0.80; 9), AP3XS (0.86, 0.90; 6) |
| spread kept (0.94-1.15) | AP3XXS (0.94, 0.84; 6), APEXM (0.98, 0.93; 6), UD4XS (1.01, 0.97; 0), GSQ3S (1.01, 0.88; 3), UD3XXS (1.02, 0.90; 0), EXL3 (1.04-1.15, 0.88-0.96; 2-14) |

**Censoring.** "Arm-side censored" counts the selected items (116; 8 of them are censored on Q8_0's side for every
arm) where Q8_0 has all three variants in its top 50 but the arm does not. The arm's value there is an upper-bound
floor, which shrinks the arm's spread and can fake compression. Where 6-43 items are floored, compression and
flooring cannot be separated.

- AD3XXS is the clearest compression: its ranking agrees with Q8_0 at r = 0.92, but its spread is 0.69.
- UD3XXS's slope of 0.92 is weaker agreement only: its spread is kept.
- **The all-variants subset does not clear truncation.** Refitting only on items where all three variants are in both
  top 50s moves every slope by at most 0.06, except EXL25 (1.01 -> 0.87). But that subset selects on the arm's
  value, which also shrinks slope and spread, so it cannot rule the artifact out. The censoring counts above are the
  check that can.

**2. At the greedy decision, one offset recovers most of the pooled shift for the timid files, but the per-template
rule fails.**
- At temperature 0 the slot abstains iff the best variant's logit beats every other token, so a bias `b` flips item
  i exactly when b crosses (best other - best variant).
- `b` was fitted on these decisions with the same cross-fit and partition. The verdict uses the tolerances as
  registered, applied to abstain rates.

| file | before: over-abstain H / answer U | after | agreement with Q8_0's decisions |
|---|---|---|---|
| AD3XXS | +0.12 / -0.14 | +0.03 / -0.01 | 0.88 -> 0.94 |
| AD3S | +0.14 / -0.15 | +0.01 / -0.02 | 0.87 -> 0.93 |
| UD3XXS | +0.18 / -0.12 | +0.03 / -0.02 | 0.87 -> 0.93 |
| APEXM | +0.04 / -0.10 | -0.01 / -0.03 | 0.92 -> 0.93 |
| AD2XS | -0.01 / +0.16 | +0.01 / +0.02 | 0.91 -> 0.93 |
| AP2S | +0.19 / -0.09 | +0.09 / +0.04 | 0.86 -> 0.87 |
| AP3XXS | +0.04 / +0.09 | +0.04 / +0.08 | 0.90 -> 0.90 |
| APEXN | -0.01 / +0.09 | +0.01 / +0.06 | 0.91 -> 0.91 |
| EXL30 | +0.01 / +0.04 | +0.01 / +0.03 | 0.95 -> 0.96 |
| EXL35 | +0.00 / +0.08 | +0.00 / +0.06 | 0.97 -> 0.97 |

- Easy items are untouched (E +0.00 after correction for every labelled file).
- **Only AD2XS passes the full verdict.** The worst cells of the other labelled files are 0.12-0.16, and 0.36 for
  AP2S, AP3XXS and APEXN.
- The cell rule is coarse at this readout: a cell holds 25 binary items, so one item is 0.04 and the 0.10 bound allows
  two items. A 0.12-0.16 cell cannot be told from noise.
- The slope synthetics do not control this readout, because an offset undoes any monotone affine logit map exactly at
  a fixed threshold.
- Even where the offset works (agreement 0.93-0.94), 6-7 % of items still disagree with Q8_0's decision. No
  threshold reaches those.

**3. The slot is still not the generation.** Slot-vs-generation kappa was 0.55-0.82 in main. Whether a live
`logit_bias` moves generations the same way is stage 2, the practical test.

## What this means for the summary

- For the **timid** files (AD3XXS, AD3S, UD3XXS, APEXM) and for AD2XS, one negative (or, for AD2XS, positive) bias
  on UNKNOWN recovers most of Q8_0's behaviour at the slot. At the registered soft readout, AD3XXS narrowly fails (0.034 against a
  0.03 bound).
- The **AP and APEX confident files** (AP3XXS, APEXN) and **AP2S** do not come back. Their shift is concentrated in one
  template (novels or capitals), which no single number can fix.
- For **greedy (temperature 0) use**, one number is enough in principle. At a fixed threshold an offset undoes any
  monotone rescaling of the logits, so compression costs nothing there. Two things limit the greedy fix:
  - template heterogeneity (one question type shifted more than the others);
  - the 6-7 % of items that disagree with Q8_0 at any threshold.
- For the **soft readout** (the probability itself, e.g. a confidence score shown to a user or a sampled decision),
  the low-bit IQ files with little censoring (AD3XXS clearest) also **compress** the UNKNOWN-vs-answer odds. A
  per-file offset fixes the mean there, not the shape.
- Every file keeps a residual that no threshold removes, the same size on both metrics (column "after"): 0.00-0.015
  for the best files, 0.04-0.10 for the 2.5-3.0 bpw GSQ and UD files, AP2S and Bonsai.

## Stage 2 choice, fixed now (before any live run)

The prereg names the full-sample soft `b`. Stage 2's practical test is greedy R-gen, where the decision-fit `b` is
the relevant one, and the two differ by 0.2-0.5 logits. **Stage 2 tests both.**
- R-slot at the soft `b` must reproduce the offline prediction.
- R-gen is scored at both values, with the decision `b` primary.
- The decision `b` is the midpoint of the full-sample minimising plateau (ties are flat intervals at this readout, and
  a plateau edge is fragile to kernel-level numerics).
- Files: the 5 labelled files fixed under H-fix, plus AD3XXS, declared now: it is the clearest compression case and
  the question is whether greedy generations can be fixed when the soft readout cannot.

| file | soft `b` (full sample) | decision plateau | decision `b` (midpoint) |
|---|---:|---|---:|
| AD2XS | +1.31 | [+0.92, +1.23] | +1.08 |
| AD3S | -1.38 | [-1.92, -1.81] | -1.87 |
| UD3XXS | -1.78 | [-2.17, -1.98] | -2.08 |
| APEXM | -0.72 | [-1.00, -1.00] | -1.00 |
| EXL35 | +0.40 | [+0.58, +0.77] | +0.68 |
| AD3XXS | -1.15 | [-1.58, -1.50] | -1.54 |

Stage 2 still needs Mark's go-ahead and .194, and gets its own run note.

**Re-scoped before any live run (2026-09-27).** When .194 came up for stage 2, main's own generations showed that the
confident files already refuse invented items at Q8_0's rate (`RESULT_MAIN.md`, Correction). A slot-fitted bias
would push their generations past Q8_0, so the registered stage 2 would mostly have measured a predictable
over-correction. The session ran the in-context slot readout instead (`PREREG_INCTX.md`), which reads P(UNKNOWN)
where generation actually decides. Stage 2 as written above was not run.

## Limits

- **Slot readout only.** Stage 2 (live `logit_bias` on .194: R-slot must reproduce the offline prediction; R-gen is
  the practical test) needs Mark's go-ahead and has not run.
- `b` is fitted against Q8_0's readout on these 240 items. A user needs the Q8_0 reference rows or labelled items to
  calibrate a file.
- The fix only covers a prompt that offers an abstain token. One model, thinking off, one prompt.
