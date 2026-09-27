# Result -- quant-abstention CALIB: one logit bias per file restores Q8_0's "I don't know" for half the shifted files; the shift is not generally an offset

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

## Limits

- **Slot readout only.** Stage 2 (live `logit_bias` on .194: R-slot must reproduce the offline prediction; R-gen is
  the practical test) needs Mark's go-ahead and has not run.
- `b` is fitted against Q8_0's readout on these 240 items. A user needs the Q8_0 reference rows or labelled items to
  calibrate a file.
- The fix only covers a prompt that offers an abstain token. One model, thinking off, one prompt.
