# RESULT: instrument v3 holds, and the judge's own date shifts precision down a little, the same way on every anchor

**Prereg:** `PREREG_INSTRUMENT_V3.md` (`d697a828`, before any v3 row). **Run:** 2026-11-02 on the 9070, kernel 7.3.1-1, the judge's file,
binary and flags. **Numbers:** `RESULT_instrument_v3.json`; text-free verdicts `verdicts_<ARM>_v3.csv`, including `L31V3`.

## Predictions

| # | claim | result |
|---|---|---|
| V1 | the pinned judge is deterministic | **held:** `L31AB` re-judged equals the 10-31 pinned pass, 1,000 of 1,000 |
| V2 | at most 1.0 % of verdicts flip on every anchor | **FAILED:** 1.8 % at most (`Q27OFF`) |
| V3 | recall and precision move at most 0.01 | **FAILED:** precision moves up to 0.039 (`S25AB`); recall at most 0.009 |
| V4 | the v3 subject run is whole and close to `L31AB` | **held:** 1,000 rows, all hashed, 1,000 distinct prompts; recall 0.577 vs 0.572 |

## Per anchor (sub1000, stored pass at its own date -> v3 pin)

| anchor | judged on | flips | recall | precision |
|---|---|---|---|---|
| `LLAMA8` | 10-24 | 13 (1.3 %) | 0.568 -> 0.558 | 0.669 -> 0.663 |
| `L31AB` | 10-28 | 4 (0.4 %) | 0.572 -> 0.568 | 0.676 -> 0.674 |
| `Q27OFF` | 10-25 | 18 (1.8 %) | 0.549 -> 0.554 | 0.800 -> 0.776 |
| `Q27ON` | 10-25 | 7 (0.7 %) | 0.483 -> 0.485 | 0.793 -> 0.788 |
| `S25AB` | 10-29 | 16 (1.6 %) | 0.410 -> 0.401 | 0.803 -> 0.764 |
| `S26AB` | 10-29 | 13 (1.3 %) | 0.343 -> 0.348 | 0.758 -> 0.734 |

**The direction is shared.** Precision falls on all six anchors. Of the 71 flips, 48 go from "not an abstention" to "an
abstention", and 23 the other way. So the pinned judge calls a few more answers abstentions.

**Where the flips land (post hoc):**
- **QASPER (questions about scientific papers):** 15 of the 71. Fourteen are answers to items that should not be abstained on,
  now judged as abstentions.
- **Next:** MMLU math and ALCUNA, 6 each, then GPQA, 5.
- **Not concentrated in the time-sensitive sets.** So the obvious story, "a judge told it is 2024 doubts recent questions", does
  not fit. It looks like borderline answers tipping under a small prompt change. Whether any other date tips them the same way
  is not tested: a second-date control on the same answers would settle it (about six minutes per anchor).

## What it means

- **v3 stands.** The point is a judge that does not change with the calendar, and V1 shows it does not. The pin is also Meta's
  own render.
- **Never compare across instrument versions.** On Spark 2.5, the judge's date alone moved precision 0.039, about the width of
  a typical interval here. Within v3 every arm meets the same judge prompt.
- **The Spark 2.5 vs 2.6 comparison is unaffected.** Both were judged on 10-29, and at the pin the gap is unchanged in kind:
  recall 0.401 vs 0.348.
- **`L31V3` is the first v3 row:** recall 0.577, precision 0.667.

## Limits

- One judge file, one engine, one card. Six anchors, flips of 4 to 18 each: the shared direction is six of six, not a
  measured bias size.
- The flip breakdown by dataset was not registered.
