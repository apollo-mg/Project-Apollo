# Result -- quant-abstention pilot: the answer-slot readout passes its gate but is weakest on Bonsai, thinking-off shows a quant effect (Bonsai confabulates on invented items), and the hard arm is too hard

**2026-09-26.** Pre-registration: `PREREG_PILOT.md` plus Deviations 1-3, all written before any model saw an item.

| | |
|---|---|
| Corpus | P0: 120 items (40 easy, 40 hard, 40 invented) |
| Analysis | `analyze_pilot.py` -> `RESULT_pilot.json` |
| Raw rows | `raw/pilot_{C,M,L,B}.jsonl` |
| Provenance | `raw/logs/meta_*.json`, `server_*.log.gz` |

## Instrument

- **Box:** `.194`, GPUs 0 and 1 (2x P100), 150 W limit, SM at 1063 MHz under load.
- **Build:** buun `0b2789f23`, sm_60, gcc-13.
- **Settings:** `-sm layer -c 4096 -ctk f16 -ctv f16 -np 1`. f16 KV was verified in every arm's log (`K (f16): 128.00 MiB, V (f16): 128.00 MiB`).
- **MTP off:** the head is logged as unused.
- **Hygiene:** a server restart per arm, one discarded warm-up request, `cache_prompt: false`.
- **Tokens:** " UNKNOWN", " Unknown" and " unknown" are single tokens in every arm (ids 59322, 21024, 9496).
- **Thinking off:** the render ends in `<think>\n\n</think>\n\n`.

| arm | file | GiB | sha256 |
|---|---|---:|---|
| C | unsloth Q8_0 (the reference; byte-identical to the desktop's verified copy) | 27.05 | `a680f44a0692` |
| M | AD IQ3_XXS | 11.25 | `71d7623c5c11` |
| L | AD IQ2_XS | 9.21 | `a437190b719a` |
| B | Ternary Bonsai 2 PQ2_0 | 6.71 | `3907dc1658db` |

## Registered decisions

| # | rule | result | decision |
|---|---|---|---|
| **P1** | R-slot vs R-gen agreement >= 85 % in every arm | C 0.896, M 0.864, L 0.900, B 0.855 | **R-slot is the main campaign's primary readout.** It passes as registered, but see "What P1 rests on": the margin over a trivial predictor is thin for B |
| **P2** | L or B differs from C on hard-arm CORRECT or invented-arm abstention (95 % CI excludes 0) | B, invented abstention **-0.194 [-0.361, -0.056]** (n 36). L: hard -0.081 [-0.189, 0.000], invented -0.026 [-0.079, 0.000], "does not differ" as registered | **Thinking-off carries the campaign**, so the medium-thinking fallback is not triggered |
| **P3** | at C: easy CORRECT >= 85 %, hard CORRECT in [25 %, 75 %] | easy **0.850** (pass, exactly at the line). Hard **0.216** (fail) | **The hard band is moved and P0 re-drawn** before the main campaign (below) |
| **P4** | sizing inputs, C vs L | discordance: ABSTAINED 0.061 (n 115); CORRECT on answerable 0.104 (n 77). R-slot paired difference: mean -0.112, **SD 0.196** (n 120) | The main N is set from these in the main prereg |

**Predictions** (checked, not gating):

| # | claim | outcome |
|---|---|---|
| Q1 | R-slot agreement >= 85 % in C and M | **held** |
| Q2 | L is timid: hard CORRECT lower, and P_abs on answerable higher, than C | **failed.** Hard CORRECT is lower (0.125 vs 0.216), but P_abs on answerable is *lower* (hard 0.112 vs 0.225) |
| Q3 | B is confident: invented abstention lower, P_abs on answerable not higher | **half.** Invented abstention is lower (0.395 vs 0.605), but hard P_abs is *higher* (0.345 vs 0.225) |
| Q4 | AUROC (invented vs easy + hard) at C >= 0.85 | **held**, 0.935 |

## Per-arm readouts (graded items; R-slot over all 120)

| arm | easy CORRECT | hard CORRECT | invented ABSTAINED | invented WRONG | hard over-abstain | mean P_abs easy / hard | mean 1-P_abs invented | AUROC pooled / within-template | not graded |
|---|---:|---:|---:|---:|---:|---|---:|---|---|
| C | 0.850 | 0.216 | 0.605 | 0.395 | 0.135 | 0.001 / 0.225 | 0.281 | 0.935 / 0.922 | 5 truncated |
| M | 0.800 | 0.226 | 0.656 | 0.344 | 0.097 | 0.018 / 0.441 | 0.195 | 0.914 / 0.901 | **17 truncated** |
| L | 0.725 | 0.125 | 0.575 | 0.425 | 0.125 | 0.003 / 0.112 | 0.507 | 0.934 / 0.922 | 0 |
| B | 0.564 | 0.125 | **0.395** | **0.605** | 0.100 | 0.008 / 0.345 | 0.408 | **0.856 / 0.850** | 1 truncated, 2 no-answer |

**Direction of failure vs C** (DESIGN's labels, applied mechanically; R-slot unless stated):
- **M** is *timid* by the letter: hard P_abs up (0.441 vs 0.225) and invented confabulation down (0.195 vs 0.281). Generation barely moves, and 17 of its items are missing (below).
- **L** fits no label. P_abs drops on answerable *and* invented items, while ranking holds (AUROC 0.934 vs 0.935) and generation barely moves. That is a uniform downward shift of the slot mass. By AFM-22 it is not called a calibration change in either direction. The timid signature L148 saw at medium thinking does **not** appear at thinking-off. The two regimes are not compared (DESIGN).
- **B** fits no label either:
  - confabulation up by both readouts (invented abstention 0.605 to 0.395; slot 0.281 to 0.408);
  - hard timidity up (0.225 to 0.345);
  - discrimination down (0.935 to 0.856).

  "Confident" requires timidity flat and "noisy" requires both flat, so neither applies. It is closest to a model that has lost the *ranking*: less sure where it should be sure, and more sure where it should not be.

## What P1 and the other gates rest on (descriptive)

**The P1 baseline is high.** Easy items almost never abstain, so a predictor that never says UNKNOWN already agrees with R-gen on most graded items:

| arm | never-abstain baseline | agreement | Cohen's kappa | slot says abstain, generation answers | slot says answer, generation abstains |
|---|---:|---:|---:|---:|---:|
| C | 0.757 | 0.896 | **0.736** | 9 | 3 |
| M | 0.767 | 0.864 | 0.684 | 14 | 0 |
| L | 0.767 | 0.900 | 0.698 | 3 | 9 |
| B | 0.838 | 0.855 | **0.581** | **15** | 2 |

- The readout is weakest in exactly the arm DESIGN said it must handle: B.
- B's errors run one way. Its answer slot puts mass on UNKNOWN on 15 items where its free generation then answers anyway. The slot is not wrong that B is unsure; the generation overrides that uncertainty.
- So in the main campaign R-gen is reported next to R-slot, and the main prereg should gate on kappa, not raw agreement.

**Truncation is not random.**
- M lost 17 items at the 256-token cap, all hard or invented. 14 of the 17 have slot P_abs > 0.5: M deliberates at length exactly where it is unsure, and those are the items P1 and P2 cannot see.
- C lost 5, and B lost 1 plus 2 with no answer line.
- The main campaign needs a larger `max_tokens` (the unanswerable arm runs longest, as CAL's budget note warned).

**Template priors are large but barely inflate the pooled AUROC.**

| invented items at C | abstained |
|---|---:|
| capitals | 9/9 |
| universities | 10/10 |
| novels | 4/10 |
| operas | **0/9** |

- The model names a composer for every invented opera, as it does for real obscure ones (hard operas: 8/10 WRONG). For operas it never declines, in any arm.
- The pooled AUROC is only slightly above the within-template mean (C 0.935 vs 0.922), so the headline is not mainly separation between templates.
- B's drop in invented abstention sits in **universities (10/10 to 4/9)** and **novels (4/10 to 1/10)**: it invents founding and publication years.
- The P2 sign count, invented abstentions: C only 8, B only 1. L: hard CORRECT, C only 3 and L only 0; invented abstained, C only 1 and L only 0. The CIs reaching exactly 0.000 reflect that every discordant pair went one way on 3-4 pairs. The registered rule gives "does not differ".

**Hand audit of every easy and hard WRONG at C (30 items).** There are **no grader misses**: no alias, diacritic or format failure.
- **23 are genuinely wrong answers.** Examples:
  - capitals: Daegu (the pre-2016 capital), Moanda, Pamekasan, Dabakala, Abidjan (pre-2011), Daugavpils;
  - operas: all 8 hard operas, such as Vivaldi for Gluck, Offenbach for Nino Rota and Salieri for Sacchini;
  - novel years such as Fletch 1979 vs 1974.
- **7 are definitional or lineage ambiguities** that the strict rule scores WRONG, as registered:
  - Kansas 1865 (chartered 1864, founded 1865, opened 1866);
  - Wrocław 1811 (the Breslau merger);
  - Kabul 1932 (sources differ, 1931 or 1932);
  - Wales Newport 1992;
  - the Academy of Internal Troops 1992;
  - UAM Cuajimalpa 1974 (the parent university);
  - 13 Bullets 2007 (print, after the 2006 online serial).
- **Sensitivity only:** counting the 4 hard ambiguities as correct would put hard CORRECT at C at 0.32, inside the range. The registered strict grade gives 0.216, and the lenient year set (Deviation 2) recovers none of them (hard lenient 0.216). P3 fails as registered.
- Novels, operas and universities in the hard arm are genuinely too hard at 3-8 sitelinks: 1 correct out of 8-10 in each at C.

## Consequences for the main campaign (to be registered in its prereg, not here)

- **Primary readout:** R-slot, as P1 decided, with R-gen co-reported. Validity is gated on kappa, with B-type arms flagged.
- **Regime:** thinking off, as P2 decided.
- **Hard band (P3):** a uniform rule, written before any redraw and **not** derived from C's per-template accuracy. All templates move to **3-20 sitelinks**, the band capitals already use (Deviation 1). Then P0 is re-drawn with the same construction code.
- **Budget:** `max_tokens` well above 256 for R-gen.
- **The opera template** carries no abstention signal in any arm (invented operas 0-1/10 abstained, hard operas 0-1/10 correct). Whether it stays is a main-prereg decision; its within-template AUROC (0.71-0.83) is the lowest.
- **N:** from P4. The R-slot paired SD of 0.196 makes the continuous readout far cheaper than the binary one. For example, detecting a 0.05 mean shift at 80 % power needs about 120 paired items, against McNemar on a 6 % discordance.

## Exploratory (not registered)

IQ2_XS and Bonsai disagree on R-gen abstention on 0/39 easy, 3/40 hard and 8/38 invented items. The mean |P_abs difference| is 0.008 easy, 0.245 hard and 0.208 invented. So disagreement between the two low-bit arms concentrates where the answer is uncertain. This is weak evidence: easy items are easy for both, so any disagreement measure would concentrate on the other arms. Whether disagreement adds anything beyond either arm's own P_abs is untested.

## Not established

- **Size and scope:** 40 items per arm, one model family, one PTQ packager (AD) plus Bonsai, thinking off only.
- **Methods:** nothing here compares quantization methods at matched bytes; that is the main campaign.
- **Pilot vs L148:** the numbers are not comparable (different regime, different corpus).
