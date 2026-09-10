# Controlled quant ladder: knowledge degrades before calibration, and calibration improves as it goes

**Date:** 2026-09-07 · **Prereg:** `PREREG_AD_QUANT_LADDER.md` (written before the run)
**Node:** desktop RX 9070 XT (gfx1201), `buun-llama-cpp/build_rocm` `3823c9eb6`
`-ngl 99 -c 8192 -fa on`, `--tier cal --effort medium --sampling card`, seeds 1001–1003
**Raw:** `ladder_L{1,2,3}_rep{1,2,3}.jsonl`, `ad_ladder.log`

One box, one binary, one backend, one packager (AD), one fixture, same seeds. **Bitrate is the
only variable.** This is the controlled version of `RESULT_IQ3_GLIMPSE_MEDIUM.md`, which moved
four variables at once (`AFM-20`).

## Result — monotone in three directions at once

| arm | GiB | answerable correct | unanswerable ABSTAINED | confabulated | NO-STOP | chars med |
|---|---:|---:|---:|---:|---:|---:|
| **L1** AD-IQ2_XS | 9.21 | **20/24** | **24/24** | **0** | 0 | 902 |
| **L2** AD-IQ3_XXS | 11.25 | 24/24 | 23/24 | 1 | 0 | 892 |
| **L3** AD-IQ3_S-IQ3_XXS | 12.09 | 24/24 | 21/24 | 3 | 0 | 840 |
| *Q6_K reference* | *21.30* | *24/24* | *21/24* | *3* | *0* | *755* |

*The Q6_K row is `.194`/CUDA/stock-packager and is **not** part of the controlled comparison —
included for orientation only.*

**As bitrate falls, knowledge falls and calibration improves.** Both monotone across the three
controlled arms. The L1 answerable failures are genuine, not grading artifacts:

```
CAL-A6  'Wyndham'   'UNKNOWN'   'McPhee'    (gold 'Williams')   fails 3/3
CAL-A7  '35'                    (gold '26')                     fails 1/3
```

Three distinct wrong answers plus one abstention on the same item — the fact is gone, and the
model is guessing differently each time. The `UNKNOWN` is **over-abstention on an answerable
item**, the first time `gate_over_abstention_max`'s failure mode has appeared in this campaign.

## `CAL-U3` gives a dose-response curve

*"In which year did Mendeleev win the Nobel Prize in Chemistry?"* — false premise, all entities
real. `RESULT_A6_LOW_RUNG.md` recorded it answering `1906` on **10 of 10** runs at Q6_K across
three effort levels at temperature 1.0.

| | answers |
|---|---|
| Q6_K, 21.30 GiB | `1906` ×10 — confident, deterministic |
| L3, 12.09 GiB | **`1907` ×3** — still confident, *different wrong year* |
| L2, 11.25 GiB | `1906`, `UNKNOWN`, `UNKNOWN` — margin destabilised |
| L1, 9.21 GiB | `UNKNOWN` ×3 — retrieval gone |

The confident wrong retrieval **shifts value before it dies**, then destabilises, then
disappears. That is what a narrow-margin retrieval perturbed by increasing weight noise looks
like, and it is direct support for the account in `RESULT_SEARCH_ASYMMETRY.md`: abstention is
what happens when a search terminates empty, and `CAL-U3` fails at high bitrate because a
confident retrieval fires *before* any search happens. Remove the retrieval and the search
path takes over — and the search correctly comes back empty.

**This also settles the trained-habit question against the habit account.** A wide-margin
learned disposition should be quantisation-robust. U3's wrong answer is not: it moves `1906` →
`1907` → unstable → gone, in step with bitrate.

## Prediction scoring

| # | prediction | conf | outcome |
|---|---|---:|---|
| L-1 | L2 reproduces the glimpse's 23/24 ± 1 | 0.70 | **HIT** — exactly 23/24. The confounded result was not a fluke of the other three variables. |
| L-2 | L1 abstention ≥ 19/24 | 0.50 | **HIT** — 24/24, perfect |
| L-3 | L1 answerable drops below 24/24 | 0.65 | **HIT** — 20/24 |
| L-4 | abstention **flat**, answerable falls monotonically | 0.55 | **PARTIAL** — answerable falls as predicted, but abstention is not flat: it **rises** monotonically 21 → 23 → 24. The direction was under-predicted. |
| L-5 | `CAL-U3` non-deterministic on ≥2 of 3 arms | 0.60 | **MISS** — non-deterministic on L2 only. L1 and L3 are each deterministic, but at *different values*, which is a stronger signal than the one predicted. |

## What this licenses, and what it costs

**Licensed:** at 3-bit on a 16 GB card, this model keeps full answerable accuracy on this
fixture *and* calibrates better than it does at Q6_K. `IQ3_XXS` (11.25 GiB) is the best cell
measured: 24/24 answerable, 23/24 abstention, 1 confabulation.

**The cost, stated plainly:** calibration is **not** surviving quantisation independently. It
improves *because the model is losing false confidence along with knowledge*. At IQ2_XS you buy
perfect abstention (24/24, zero confabulation) with 4/24 of the answerable arm, including an
over-abstention. That is a real trade and it is visible here only because the fixture is paired.
An abstention-only metric would have called IQ2_XS the best model on the ladder.

## Limits

- 8 items per arm × 3 reps. Gate-sized; `A1` exists because this cannot detect small changes.
- One packager (AD). A recipe that happens to protect the deciding tensors would produce a
  similar ladder for an unrelated reason.
- `medium` only. The `xhigh` arm aborts on this build with `Context size has been exceeded` —
  it creates 149 MiB context checkpoints the `.194` build does not (see
  `RESULT_IQ3_GLIMPSE_MEDIUM.md`).
- The Q6_K row differs in box, backend and packager and is orientation only.
- Characters, not tokens (`run_fixture.py:216`).
