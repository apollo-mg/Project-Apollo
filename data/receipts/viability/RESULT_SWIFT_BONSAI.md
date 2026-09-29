# Result -- Swift-Bonsai-2 does not fib less than Bonsai 2, and it does not fib more. It thinks 27 % less on false premises and keeps the same honesty: unlike Swift on the 27B, the brevity costs nothing here.

**2026-09-28.** Pre-registration `PREREG_SWIFT_BONSAI.md` (`cafdfad`); runner `run_swift_bonsai.sh` (verified
servers); analysis `analyze_swift_bonsai.py`, committed with the prereg and self-tested on stored Bonsai arms.

- **Raw:**
  - stage 1: `../quant-abstention/raw/main_{BONB9,SWB9}.jsonl`, 240 rows each;
  - stage 2: `swift_bonsai/{BONB9,SWB9}/armA_rep{1,2,3}.jsonl`, 48 each.
- **Setup:** RX 9070 XT, prism `9a9394a89` build_hip, both models in PQ2_0 (7,206,168,928 bytes each; 1.4 % of the
  bytes differ, spread over 681/851 tensors), `-c 16384`, f16 KV.

## Stage 1 -- M1, thinking off (100 invented questions)

| model | easy | hard | **invented: refused** |
|---|---:|---:|---:|
| base Bonsai 2 (BONB9) | 0.57 | 0.18 | **0.40** |
| Swift-Bonsai-2 (SWB9) | 0.55 | 0.19 | **0.40** |

**Swift minus base:** refused +0.000 [+0.000, +0.000]; hard correct +0.010 [+0.000, +0.030].

The two are near-twins without thinking: the same grade on 237/240 items, identical answer text on 211/240, median
|dP(UNKNOWN)| 0.0007. The Swift correction acts on reasoning and leaves the direct answers almost untouched. **Both
answer 60 of 100 invented questions.**

## Stage 2 -- CAL at `xhigh`, thinking on, 3 seeds

| model | answerable (graded / corrected, AFM-51) | unanswerable abstained | wrong | NO-STOP | median reasoning, unanswerable |
|---|---:|---:|---:|---:|---:|
| base | 23 / **24** | 15/24 | 6 | 3 | 3,002 ch |
| Swift | 22 / **24** | 17/24 | 5 | 2 | **2,184 ch** (0.73x) |

The answerable "misses" are `weber (Wb)` grader false negatives.

## Registered verdicts

| # | claim | result |
|---|---|---|
| S1 | Swift does not fib less (M1: refusal CI lower bound <= 0) | **holds.** Identical |
| S2 | knowledge unchanged (hard-accuracy CI includes 0) | **holds** |
| S3 | Swift thinks <= 0.8x on false premises (CAL) | **holds.** 0.73x |
| S4 | thinking less does not buy honesty (Swift abstained <= base) | **does not hold.** 17 vs 15, the other way, but p = 0.76: no difference |

## What it means

- **"Does it fib less?" No, and it does not fib more either.** Without thinking it is the same model (60 % of
  invented questions answered). With thinking, it abstains on the same share of fakes (17 vs 15 of 24, p = 0.76),
  with no more wrong answers (5 vs 6) and no more runaways (2 vs 3).
- **The efficiency claim checks out where it matters:** -27 % reasoning on false premises, -3 % on answerable
  questions. The card claims 39.8 % fewer thinking tokens overall.
- **This differs from Swift on the 27B** (`RESULT_SWIFT_BREVITY_TAX.md`: -26 % thinking on false premises and a
  6-vs-4 trend toward more confabulation). On Bonsai the same kind of cut shows no honesty cost. A consistent
  reading, not tested: Bonsai's own long deliberation on fakes (3,002 chars median against the 27B's ~2,275) had more
  slack to cut.
- **Bonsai 2 is still a heavy fibber at thinking-off**, with or without Swift: 0.40 refused, where the 27B Q8_0
  refuses 0.60 on the same set. Swift fixes length, not calibration.

## Not established

- 24 unanswerable attempts per model in stage 2, so only large differences are detectable. S4's 2-item difference
  is noise.
- One pack (PQ2_0), one card, one build. PTQ1_0 not run (the two packings behaved as one model on .194's M1).
