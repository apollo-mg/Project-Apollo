# Result -- Flash-Next at 2 bits knows far more than Qwen3.8-27B at 8 bits (hard-question accuracy 0.79 vs 0.50), confabulates less (refuses 0.71 vs 0.60 of invented items), and loses almost nothing to its own IQ4 (+0.02)

**2026-09-28.** Pre-registration `PREREG_FLASHNEXT.md` (`293911e`), with Deviation 1 (`5ed47ba`: the first attempt ran
all arms on one stale server; its files are kept in `raw/invalid_20260928/`) and Deviation 2 (`7f6a880`: IQ4 at
`-ngl 44`, since the registered expert-spill rule could not load it). Analysis `analyze_flashnext.py`, committed and
self-tested on stored 27B arms before any Flash-Next row existed. Output `RESULT_flashnext.json`. Raw
`raw/main_FNQ2.jsonl`, `raw/main_FNIQ4.jsonl`, `raw/main_FNQ2X.jsonl`; runner log `raw/logs/flashnext_arms.log`.

**Instrument:**
- .194, 4x Tesla P100 at 150 W / 1063 MHz (read back in each arm's header), buun `0b2789f23` (the main campaign's
  build), `-sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off`;
- M1 (240 Wikidata-built items: 40 easy, 100 hard answerable, 100 invented), thinking off, temp 0;
- every arm on a fresh, verified server: its own log said the model loaded, `/props` named the arm's file, and the
  offload line matched the arm's placement.

**Model and tokenizer:** Flash-Next (qwen4exp) shares Qwen3.8's UNKNOWN token ids (59322 / 21024 / 9496), so the 27B
arms are a direct reference on the same corpus, prompt and grader.

## Results

| arm | easy correct | hard correct | invented: refused | hard: abstained |
|---|---:|---:|---:|---:|
| **FNQ2**: Flash-Next UD-Q2_K_XL, 49/49 layers on GPU | 0.90 | **0.79** | **0.71** | 0.01 |
| **FNIQ4**: Flash-Next UD-IQ4_XS (87.24 GiB), `-ngl 44` | 0.95 | **0.81** | **0.71** | 0.01 |
| FNQ2X: Q2 at `-ngl 44` (placement control) | 0.90 | 0.79 | 0.71 | 0.01 |
| 27B Q8_0 (`main_C.A`) | 0.85 | 0.50 | 0.60 | 0.03 |
| 27B UD-Q2_K_XL (`main_UDQ2KXL`) | 0.825 | 0.35 | 0.61 | 0.03 |

## Registered verdicts

Paired by item, 95 % percentile bootstrap (10,000 resamples):

| # | claim | result |
|---|---|---|
| P1 | knowledge before calibration inside Flash-Next: IQ4 - Q2 hard accuracy >= 0.05, CI > 0; refusal within +/-0.07 | **does not hold.** +0.02 [-0.04, +0.08]; refusal +0.00 [-0.04, +0.04] |
| P2 | scale buys knowledge: FNIQ4 - 27B Q8_0 >= 0.05, CI > 0 | **holds.** +0.31 [+0.21, +0.41] |
| P3 | 2-bit MoE >= 8-bit 27B: FNQ2 - 27B Q8_0 >= 0, CI > -0.05 | **holds.** +0.29 [+0.19, +0.39] |
| P4 | CPU placement is inert for behaviour: same grade on >= 95 % | **holds.** 240/240 |

**Reported without a prediction:** invented-item refusal against 27B Q8_0 is **+0.11 [+0.03, +0.19]** for both
Flash-Next arms.

## What it means

- **At 2 bits Flash-Next keeps its knowledge; the 27B did not.**
  - On this corpus the 27B loses 15 points of hard-question accuracy from Q8_0 to Q2_K_XL (0.50 to 0.35).
  - Flash-Next loses 2 points from IQ4 to Q2_K_XL, inside the interval of zero.
  - P1 was registered on the 27B's pattern, and it failed.
  - A reading, not tested here: a big sparse MoE spreads each fact over far more stored weights than a dense 27B, so
    2-bit rounding costs it less. The practical consequence is tested: **Q2 is enough for Flash-Next** on
    knowledge, and IQ4's extra 37 GiB and slower placement buy nothing measurable.
- **The 2-bit Flash-Next beats the 8-bit 27B by 29 points on hard questions and refuses invented ones more
  often.**
  - The fleet serves the 27B as its daily driver at Q6_K on .73.
  - On factual knowledge and calibration, Flash-Next Q2 on .194 (21 tok/s fully resident, per
    `qwen4exp/RESULT_FLASHNEXT_RESIDENCY.md`) is the better model by a wide margin.
- **Placement is numerically real but behaviourally inert.** FNQ2 against FNQ2X (four whole layers moved to the CPU):
  - P(UNKNOWN) differs on 190/240 items (median |dP| 3.3e-4, max 0.12);
  - the generated wording differs on 123/240;
  - **no grade changes.**

  This is the control that distinguishes a real placement test from the invalid first attempt, which was 240/240
  identical in every field.
- **Repeatability (exploratory, from Deviation 1):** FNQ2 repeats the invalid attempt's Q2 run 240/240 across
  server boots.

## Not established

- **One kind of test.** Short factual questions about capitals, novels, operas and universities, thinking off,
  temp 0, one prompt. This measures stored knowledge and willingness to say UNKNOWN. It does not measure reasoning,
  stopping (thinking on, Stage B), tool use or agent outcomes (Stage C). A knowledge test favours total parameters;
  Flash-Next's advantage elsewhere may be smaller.
- **Two quants of one model.** "Q2 costs nothing" is shown for UD-Q2_K_XL against UD-IQ4_XS, not against a
  full-precision Flash-Next, which does not fit this fleet.
- **n = 100 per group.** The intervals are about +/-0.08-0.10 on differences. The 29-31 point gaps are far outside
  them; P1's 2 points are not.
- **Speed.** Arm wall-clocks (FNQ2 25 min, FNIQ4 40 min, FNQ2X 34 min) include the scoring pipeline and are not a
  speed claim. Power and clocks were recorded for BACKLOG N11 but not analysed.
