# Result -- quant-abstention MAIN: 2.5-4.5 bpw quants keep the ranking of "I know" vs "I don't" but shift the threshold, in directions set by the file, not the family

**2026-09-27.**

| | |
|---|---|
| Pre-registration | `PREREG_MAIN.md` (commit `2646d42`, before any main item ran) |
| Corpus | M1: 240 items, sha256 `bda1cfb2...` (40 easy / 100 hard / 100 invented) |
| Analysis | `analyze_main.py` -> `RESULT_main.json`, written before the run and checked against the pilot |
| Raw rows | `raw/main_<arm>.jsonl` |
| Provenance | `raw/logs/main_meta_*.json`, `main_server_*.log.gz`, `raw/main_lanes.log` |

## Instrument and run

- **Box and build:** `.194`, buun `0b2789f23` sm_60, two lanes (GPUs 0+1 and 2+3).
- **Settings:** `-sm layer -c 4096 -ctk f16 -ctv f16 -np 1`, thinking off, `cache_prompt: false`, R-gen 1024 tokens.
- **Timing:** 2026-09-26 20:23 to 2026-09-27 08:41, 23 arms plus the ceiling on both lanes.
- **Integration smoke test** before the run: 5 items, 2 arms, full path. Its outputs were deleted before the run.
- **Bridge:** Q8_0 on both lanes over all 240 items gave **bit-identical** answer-slot top-50 logprobs (max difference
  0.0) and byte-identical generations. Both lanes were used.
- **Every arm verified:**
  - sha256 equal to `arms_main.json` after staging;
  - `K (f16) ... V (f16)` in its log, and no MTP or draft line (EXL3 included: its `nextn` tensors are logged
    "unused -- ignoring");
  - the ceiling's rendered prompt tail and UNKNOWN token ids (59322 / 21024 / 9496).
- **Truncation** at 1024 tokens: at most 6 of 240 per arm (UD IQ3_XXS). No arm near the 10 % flag.
- **Band check:** hard CORRECT at Q8_0 is **0.505**. It was reported, not acted on, and sits in the middle of the 25-75 %
  range: the 9-39 band works.

## Registered verdicts

| hypothesis | verdict | what it rests on |
|---|---|---|
| **H-method** (two PTQ families, same byte bin, opposite directions) | **supported** by the registered rule | 3 pairs: bin [2.4, 2.9) AP IQ2_S *timid* vs AD IQ2_XS *confident*; bin [3.7, 4.2) AD IQ3_S and APEX I-Mini *timid* vs EXL3 3.0 *confident*. **But every pair includes a label driven by the opera template** (see Robustness) |
| **H-knee** (a common knee in discrimination) | **not supported** | Only GSQ-RCO degrades at all (IQ2_XS at 2.50 bpw; interval upper bound **-0.001**). AD, UD and AP show no distinguishable rung: "no knee in range" |

## Per-arm results

Differences are arm minus Q8_0 over the same items, with 99.917 % intervals for PTQ arms and 95 % for Bonsai.

| arm | scored bpw | timidity (H `P_abs`) | confabulation (U 1-`P_abs`) | discrimination (within-template AUROC) | kappa | label |
|---|---:|---|---|---|---:|---|
| GSQ IQ2_XS | 2.50 | +0.223 [+0.121, +0.326] | -0.085 [-0.181, +0.011] | **-0.044 [-0.093, -0.001]** | 0.55 | none |
| GSQ IQ2_S | 2.75 | +0.036 [-0.006, +0.079] | +0.056 [-0.004, +0.116] | -0.013 [-0.049, +0.014] | 0.67 | none |
| AP IQ2_S | 2.75 | +0.165 [+0.087, +0.242] | -0.074 [-0.145, **-0.003**] | -0.021 [-0.058, +0.006] | 0.56 | timid |
| UD Q2_K_XL | 2.82 | +0.032 [-0.008, +0.071] | +0.074 [-0.003, +0.151] | -0.014 [-0.053, +0.020] | 0.67 | none |
| AD IQ2_XS | 2.85 | -0.028 [-0.065, +0.008] | **+0.213 [+0.146, +0.279]** | -0.007 [-0.036, +0.019] | 0.70 | confident |
| GSQ IQ3_XXS | 3.00 | +0.105 [+0.038, +0.172] | -0.005 [-0.073, +0.063] | -0.026 [-0.067, +0.006] | 0.70 | none |
| UD IQ2_M | 3.00 | +0.065 [+0.012, +0.118] | +0.015 [-0.048, +0.079] | -0.014 [-0.045, +0.011] | 0.68 | none |
| AP IQ3_XXS | 3.09 | +0.017 [-0.024, +0.058] | +0.076 [+0.011, +0.142] | -0.013 [-0.042, +0.010] | 0.72 | confident |
| APEX I-Nano | 3.21 | -0.000 [-0.038, +0.038] | +0.113 [+0.034, +0.192] | -0.006 [-0.035, +0.020] | 0.62 | confident |
| AP IQ3_XS | 3.31 | +0.017 [-0.007, +0.041] | +0.027 [-0.020, +0.074] | -0.005 [-0.027, +0.017] | 0.81 | none |
| AP IQ3_S | 3.47 | +0.062 [+0.024, +0.100] | -0.050 [-0.103, +0.003] | -0.003 [-0.029, +0.021] | 0.74 | none |
| UD IQ3_XXS | 3.48 | +0.155 [+0.089, +0.220] | -0.144 [-0.210, -0.078] | -0.017 [-0.054, +0.011] | 0.60 | timid |
| GSQ IQ3_S | 3.50 | +0.013 [-0.024, +0.049] | +0.021 [-0.024, +0.066] | -0.003 [-0.025, +0.019] | 0.78 | none |
| AD IQ3_XXS | 3.50 | +0.121 [+0.066, +0.176] | -0.112 [-0.171, -0.054] | -0.004 [-0.024, +0.017] | 0.70 | timid |
| EXL3 2.5 | 3.59 | +0.036 [-0.005, +0.078] | -0.044 [-0.098, +0.010] | -0.018 [-0.054, +0.012] | 0.76 | none |
| AD IQ3_S-mix | 3.77 | +0.106 [+0.055, +0.157] | -0.133 [-0.194, -0.073] | +0.008 [-0.012, +0.032] | 0.69 | timid |
| APEX I-Mini | 4.01 | +0.037 [**+0.001**, +0.072] | -0.073 [-0.118, -0.028] | +0.009 [-0.008, +0.032] | 0.69 | timid |
| EXL3 3.0 | 4.05 | +0.008 [-0.018, +0.034] | +0.061 [+0.018, +0.105] | -0.014 [-0.044, +0.008] | 0.82 | confident |
| UD IQ4_XS | 4.13 | +0.024 [-0.000, +0.049] | -0.031 [-0.060, -0.002] | -0.006 [-0.026, +0.008] | 0.72 | none |
| EXL3 3.5 | 4.50 | -0.001 [-0.019, +0.018] | +0.054 [+0.020, +0.088] | -0.013 [-0.039, +0.004] | 0.80 | confident |
| Bonsai PTQ1_0 (95 %) | 1.77 | +0.066 [+0.035, +0.096] | +0.076 [+0.019, +0.134] | **-0.038 [-0.067, -0.011]** | 0.67 | mixed |
| Bonsai PQ2_0 (95 %) | 2.14 | +0.066 [+0.035, +0.097] | +0.077 [+0.019, +0.134] | **-0.038 [-0.067, -0.011]** | 0.64 | mixed |

**Validity:** every arm passes the kappa gate (>= 0.5), with a range of 0.55-0.82, so every label uses R-slot.

**Knowledge** (R-gen CORRECT, strict):
- Q8_0: easy 0.85, hard 0.505.
- PTQ arms: easy 0.67-0.88, hard 0.22-0.49.
- Bonsai: easy 0.56, hard 0.19.

The invented-item WRONG rate is 0.39 at Q8_0, 0.26-0.45 across PTQ arms, and 0.57 for Bonsai.

## What holds up

**1. Discrimination is preserved. The ranking of "knows" vs "doesn't" survives quantization down to about 2.5 bpw.**
- Across all 20 PTQ arms from 2.50 to 4.50 scored bpw, the within-template AUROC moves by at most **0.044**. 19 of
  the 20 are within ±0.03, and only GSQ IQ2_XS is distinguishable from Q8_0, on a knife edge.
- With the registered MDE (half-width about 0.02-0.04), this is **"preserved to within about ±0.03"**, not
  "unchanged".
- It is why H-knee fails: there is nothing to put a knee in.
- The only arms that clearly lose ranking are Bonsai's (-0.038, 95 %).

**2. The threshold moves, in both directions, and the direction belongs to the file, not the family.**

Arms whose labels hold on **every** template (per-template shifts of the same sign and similar size):
- **AD IQ2_XS is confident.** Confabulation is +0.24 / +0.22 / +0.18 / +0.21 on capitals / novels / operas /
  universities. It replicates the pilot's +0.226 on a different hard and invented set.
- **AD IQ3_XXS and AD IQ3_S-mix are timid.** Pilot IQ3_XXS was also timid.
- **UD IQ3_XXS is timid.**

**The family does not set the direction.** Labels in scored-bpw order:

| family | labels |
|---|---|
| AD | confident -> timid -> timid |
| AP | timid -> confident -> none -> none |
| APEX | confident -> timid |
| EXL3 | none -> confident -> confident |
| UD | none -> none -> timid -> none |
| GSQ-RCO | none throughout |

The registered H-method test passes whenever *any* two files from different families disagree in a bin. It cannot
tell "method" from "file", and within families the direction flips with bit-width. Within any single byte bin there
are **0** within-family opposite pairs, and 3 between-family pairs.

**3. Bonsai 2's two files are almost the same model.**
- PTQ1_0 and PQ2_0 (different sha256, run on different lanes) generate **identical text on 222 of 240 items**.
  `P_abs` never differs by more than 0.014.
- Both are "mixed": timidity *and* confabulation up, and ranking down. That is the only failure shape in the run that
  loses discrimination.
- It matches the pilot's Bonsai reading (mixed, AUROC down).

## Robustness (registered)

**Without operas,** H-method is **not** supported. The detail shows it is the opera template, not lost power:

| label | full corpus | without operas | on opera items |
|---|---:|---:|---:|
| AP IQ2_S "confabulation down" | -0.074 | -0.015 | -0.250 |
| EXL3 3.0 "confabulation up" | +0.061 | +0.014 | +0.205 |

The labels that hold without operas are the per-template-consistent ones above: AD IQ2_XS, AD IQ3_S, APEX I-Mini
(confabulation -0.079 without operas), AD IQ3_XXS and UD IQ3_XXS. None of them forms an opposite pair within one
byte bin. Opera is the template where the pilot showed R-gen carries no signal (invented operas are never refused),
so it is the one template where the slot readout cannot be checked against generation.

**Knife edges, stated with the verdicts:**
- AP IQ2_S confabulation, upper bound **-0.003**, and its kappa is 0.56 (second lowest);
- APEX I-Mini timidity, lower bound **+0.001**;
- GSQ IQ2_XS discrimination, upper bound **-0.001** (the only "knee").

**Pilot replication:** the three arms the pilot and main share point the same way on a new hard set (the easy items
are identical; 40 of 100 invented items overlap): AD IQ2_XS confident, AD IQ3_XXS timid, Bonsai PQ2_0 mixed with
AUROC down.

## What this means for someone choosing a quant

- At 2.5-4.5 bpw, a PTQ quant of Qwen3.8-27B still **ranks** unanswerable questions above answerable ones about as
  well as Q8_0. What moves is **where it draws the line**, and that is file-specific:
  - AD IQ2_XS answers invented questions it should refuse (confabulation +0.21);
  - AD IQ3_XXS, one rung up, refuses more (timidity +0.12).
- Calibration therefore cannot be read off the label, the family or the size. It has to be measured per file. It is
  also what KLD- and perplexity-style quant reports never show.
- The ceiling itself refuses only 61 % of invented items and answers 39 % (thinking off, CAL prompt). The shifts
  above are relative to a model that already confabulates often at this effort.

## Not established

- **Scope:** one model family, thinking off, one prompt.
- **Mechanism:** why a given file shifts the way it does.
- **Family traits:** whether direction belongs to a *family* (the within-family flips argue against it).
- **Bonsai's training:** unknown. Bonsai is not a PTQ data point.
- **EXL3 at low bpw:** EXL3 cannot reach below 3.59 scored bpw, because its embeddings are fp16.
