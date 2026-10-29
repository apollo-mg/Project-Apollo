# RESULT: 500 items failed the registered check, so the frozen instrument is 1,000 (AbstentionBench-sub1000/norefs v1)

**Prereg:** `PREREG_ABENCH_SUBSET.md` (`9c6497d0`), committed with `make_subset.py`, `check_subset.py` and both subset files
before any subset number was computed. **Data:** the stored norefs verdicts of LLAMA8 (`verdicts_LLAMA8.csv`) and the
27B OFF/ON pairs (`verdicts_Q27.csv`). **Numbers:** `RESULT_abench_subset_500.json`, `RESULT_abench_subset_1000.json`.

## sub500: FAIL (1 of 12 outside)

The 27B thinking-off arm's abstention recall: full set 0.520, sub500 0.596 [0.530, 0.659]. The full value sits 0.010
below the interval. The other 11 were inside. The draw happened to over-include items where the thinking-off arm abstains.
The same draw put the reported ON - OFF recall difference at -0.101 [-0.165, -0.032], against -0.044 on the full set.

## sub1000 (the registered fallback, same ranking, sub500 contained): PASS (12 of 12 inside)

| anchor | recall full / sub1000 | precision full / sub1000 | missing-info full / sub1000 | false-premise full / sub1000 |
|---|---|---|---|---|
| Llama 3.1 8B | 0.562 / 0.568 | 0.665 / 0.668 | 0.614 / 0.605 | 0.441 / 0.491 |
| Qwen3.8-27B, thinking off | 0.520 / 0.549 | 0.796 / 0.800 | 0.468 / 0.488 | 0.441 / 0.473 |
| Qwen3.8-27B, thinking on | 0.476 / 0.483 | 0.781 / 0.793 | 0.275 / 0.267 | 0.550 / 0.527 |

Reported: ON - OFF recall on sub1000 is -0.066 [-0.112, -0.021] (n = 437), against -0.044 on the full set. The sign is
kept, and here the interval excludes zero, but the prereg did not expect the subset to resolve this and does not rely on it.

## What it means

- **The release-day AbstentionBench row uses 1,000 items:** half the fast subset's generation and judging time, not the
  quarter hoped for. Resolution: recall +-0.047, missing-info +-0.103, false-premise +-0.128 (worst case).
- **The fallback did its job.** Registering it before computing anything is what turned a narrow miss into a decision
  rather than a reseed.
- **Still a sanity check, not a validation:** this is item-sampling error on the same verdicts, and two of the three
  anchors are one model. The sub1000 values run slightly high for the thinking-off 27B (+0.029 recall), within the
  interval. That is a reminder that sub1000 numbers are their own instrument, never mixed with fast-subset numbers.
- **Frozen by content:** `subset_1000.csv` holds each question's sha256. `make_subset.py --verify` must pass before every
  run.
