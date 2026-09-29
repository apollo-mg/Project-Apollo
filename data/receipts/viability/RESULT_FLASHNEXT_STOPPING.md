# Result -- with thinking on at `xhigh`, Flash-Next at 2 bits stops as well as its IQ4 and the 27B (2 runaways each of 48) and refuses more invented questions than the 27B (21/24 vs 19/24). Stage A's "Q2 costs nothing" holds once the model reasons.

**2026-09-28.** Pre-registration `PREREG_FLASHNEXT_STOPPING.md` (`d75e2f8`); runner `run_flashnext_stopping.sh`
(verified servers); analysis `analyze_flashnext_stopping.py`, committed with the prereg and self-tested on the
reference.

- **Raw:** `flashnext_stop/{FNQ2,FNIQ4}/armA_rep{1,2,3}.jsonl`, 96 rows, 0 errors.
- **Model and host:** .194, 4x P100 at 150 W / 1063 MHz; Flash-Next UD-Q2_K_XL (`-ngl 99`) and UD-IQ4_XS
  (`-ngl 44`); `-c 16384`.
- **Harness:** the 16 CAL items at `xhigh`, card sampling (identical to Flash-Next's own card), seeds 1001-1003,
  unchanged from the 27B Q6_K reference (`overthink_q6k` arm A).

## Results

| arm | answerable correct | unanswerable abstained | wrong | NO-STOP | median reasoning |
|---|---:|---:|---:|---:|---:|
| **FNQ2** | 22/24 (**24/24 corrected**, see below) | **21/24** | 1 | 2 | 712 ch |
| FNIQ4 | 24/24 | 22/24 | 0 | 2 | 594 ch |
| 27B Q6_K (reference) | 24/24 | 19/24 | 3 | 2 | 753 ch |

| # | prediction | result |
|---|---|---|
| B1 | Q2 NO-STOP <= IQ4 + 2 | **holds.** 2 vs 2 |
| B2 | Q2 NO-STOP <= 27B + 2 | **holds.** 2 vs 2 |
| B3 | Q2 unanswerable ABSTAINED >= 17 | **holds.** 21 |
| B4 | Q2 answerable CORRECT >= 22 | **holds.** 22 as graded, 24 corrected |

## What happened, item by item

- **The runaways are the same trap across all three models.**
  - FNQ2 ran away on `CAL-U2` ("the SI unit of thermal permittivity", a nonexistent quantity built from real
    vocabulary) and `CAL-U4` ("the default port of the Distributed Ledger Sync Protocol", a nonexistent standard).
  - FNIQ4 ran away on `CAL-U2` twice.
  - The 27B's two were `CAL-U2` and `CAL-U4`.
  - Plausible-sounding technical fakes are what makes all three search past 12,288 tokens, independent of size,
    architecture and quant.
- **Q2's one confabulation** was `CAL-U6` (a nonexistent Le Guin novel), answered "1978" once of three. The 27B's
  three wrongs were all `CAL-U3` (the Mendeleev Nobel year it answers 1906 deterministically).
- **Q2's two answerable "wrongs" are grader false negatives.** `CAL-A2` ("the SI unit of magnetic flux", gold
  "weber") was answered **"weber (Wb)"** and graded ANSWERED-WRONG. The fixture's `answer_matches` keeps the
  parenthetical symbol. This rejects correct answers across many CAL receipts (`FAILURE_MODES.md` AFM-51). The
  prediction holds either way.

## What it means

- **Thinking on, 2 bits still costs Flash-Next nothing measurable.** It stops as reliably as its IQ4 and as the
  27B Q6_K, answers every answerable item (corrected), and refuses more invented questions than the 27B.
- Reasoning lengths are all of a size: medians 594-753 chars. There is no sign of the Bonsai-style long-tail
  damage at 2 bits.
- Together with Stage A: **Flash-Next UD-Q2_K_XL is the stronger model than the 27B on both knowledge and
  calibration, and it stops as well**, on these instruments. Stage C (agent tasks) is what is left.

## Not established

- 16 items x 3 seeds. The runaway counts (2 each) are too small to rank the models on stopping; they rule out a
  large failure only.
- The reference ran on 2 GPUs with `-sm tensor`, Flash-Next on 4 with `-sm layer`. Behaviour is compared, speed is not.
