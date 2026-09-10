# The effort ladder completed: `medium` and `low` are indistinguishable on calibration; `xhigh` is the outlier — and one item is immune to all three

**Date:** 2026-09-07 · **Node:** `.194`, 4× P100 (sm_60), 1063 MHz / 150 W
**Stack:** `~/llama_stock/build_puzzle/bin/llama-server` (tree `73a55486c`, built 2026-07-15),
`Qwen3.8-27B-Q6_K`, `-ngl 99 -c 8192 -sm layer`, f16 KV, `n_ctx_slot 8192`, `n_slots 4`
**Sampling:** card thinking mode — `temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0`
**Reps:** seeds 1001–1003, paired by seed with the 2026-08-21 medium/xhigh arms
**Prereg:** `PREREG_A6_LOW_RUNG.md` (written before the run) · **Raw:** `card_low_rep{1,2,3}.jsonl`, `low_run.log`

The `low` rung was the ladder's missing cell. `medium` and `xhigh` were run 2026-08-21;
this run used the same binary, model, flags and seeds so the three are comparable.
`-c 8192` was kept deliberately — it caps escalation at 7168, which is the ceiling the
NO-STOP counts in the other two arms were measured against.

## Result — tier_cal calibration arm, 24 items per arm (8 items × 3 reps)

| | `xhigh` | `medium` | `low` |
|---|---:|---:|---:|
| answerable ANSWERED-CORRECT | 24/24 | 24/24 | 24/24 |
| unanswerable ABSTAINED | 13/24 | **21/24** | **21/24** |
| unanswerable ANSWERED-WRONG | 6/24 | **3/24** | **3/24** |
| unanswerable NO-STOP | **5/24** | 0/24 | 0/24 |
| unanswerable chars median | 5,829 | 1,052 | **921** |
| unanswerable chars max | 24,062 | 2,005 | **1,543** |
| unanswerable chars total | 196,127 | 28,386 | **22,622** |
| answerable chars median | 614 | 407 | **342** |
| unanswerable / answerable chars | 13.81× | 2.62× | **2.29×** |
| items failing ≥1 rep | U2, U3, U4, U5, U8 | **U3 only** | **U3 only** |

`medium` and `low` are **identical on every calibration count** — same abstention, same
confabulation, same zero NO-STOP, same single failing item. They differ only in verbosity,
where `low` is ~12% shorter. `xhigh` is the outlier, and it is the only arm that fails to
terminate.

## The finding that matters more than the ladder: `CAL-U3` is immune to effort

> *"In which year did Dmitri Mendeleev win the Nobel Prize in Chemistry?"* — gold `UNKNOWN`.
> Mendeleev was nominated and never won. Every noun is real; only the presupposition is false.

**All nine runs — 3 reps × 3 effort levels — answered `1906`. Every one `finish=stop`.**

At `temperature=1.0, top_p=0.95, top_k=20` that is not sampling noise. Nine independent
samples across three prompt variants produced one identical wrong year, confidently and
without hesitation. (1906 is the year Mendeleev was nominated and lost to Moissan by a single
vote — the association is real; only the outcome is inverted.)

This reframes the confabulation metric. **The "3/24" at `medium` and `low` is not a rate — it
is one item failing 3 out of 3 times.** The remaining seven unanswerable items abstain
perfectly at both levels. So reasoning effort governs whether the model confabulates on
*marginal* false-premise items (`xhigh` adds U2, U4, U5, U8 on top of U3); it does **nothing**
for an item where the model holds a confident, specific, wrong association.

No amount of deliberation repairs a false belief the model does not know it holds. That is a
different failure from over-reaching under-constrained deliberation, and the fixture is
currently measuring both under one label.

## Prediction scoring (from `PREREG_A6_LOW_RUNG.md`)

| # | prediction | conf | outcome |
|---|---|---:|---|
| P1 | `low` ABSTAINED ≥ 21/24 | 0.55 | **HIT** — exactly 21/24 |
| P2 | `low` NO-STOP = 0/24 | 0.85 | **HIT** — 0/24 |
| P3 | `low` answerable < 24/24 (brevity costs an item) | 0.45 | **MISS** — 24/24, no cost at all |
| P4 | `low` unanswerable chars median < 1,052 | 0.80 | **HIT** — 921 |
| P5 | ladder is non-monotonic; `low` diverges from `medium` | 0.50 | **PARTIAL** — see below |
| P6 | `CAL-U3` fails ≥1 rep at `low` | 0.60 | **HIT** — and 3/3, the sole failure |

**P5 deserves the detail.** It predicted `low` would *differ* from `medium`, on the reasoning
that the template has no `medium` branch (medium injects nothing) while `low` injects an
instruction — so they are structurally different interventions, not adjacent rungs. The
prediction was half right in a way that does not favour it: `low` did not continue the
xhigh→medium improvement, it **plateaued exactly**. But the predicted *divergence* did not
appear either — the two arms are identical on every calibration count. The structural
difference between "no instruction" and "an instruction to be brief" is real in the template
and produces **no measurable difference in abstention behaviour**, only ~12% less output.
Scored as a partial hit on shape, a miss on mechanism.

## The prereg's falsification check, resolved

The prereg stated: if `low` produced NO-STOP > 0/24 where `medium` produced 0/24, then
"less effort → fewer runaways" fails as a general claim. **`low` produced 0/24.** The A6
headline survives: at this model's published sampling, NO-STOP is an `xhigh` phenomenon.

## Limits

- **8 items, 3 reps.** This is the v0 *gate*; `A1` exists because 16 items cannot detect a
  small change. The `xhigh` vs `medium`/`low` gap is large and consistent; the medium-vs-low
  comparison is a null on a tiny sample and should not be read as "proven identical".
- **Characters, not tokens.** `run_fixture.py:216` records `len(content)+len(reasoning)`.
  No token counts exist in this data — see `RESULT_A6_EFFORT_NOT_SAMPLING.md` on why this
  blocks re-deriving A5's budget.
- One node, one quant (`.194`/Q6_K). `CAL-U5` behaved differently on `AD-IQ3_XXS`/RDNA4.
- `preserve_thinking` / `--reasoning-preserve` was **not** enabled, matching 08-21.
- **A third-party measurement disagrees on direction.** Artificial Analysis publishes
  AA-Omniscience Non-Hallucination at xhigh 70% / low 47% / medium 33% — i.e. medium worst.
  Their Intelligence Index marks **medium and low as estimates** ("independent evaluation
  forthcoming"), with only xhigh solid, so it is unclear how much of that spread is measured.
  Recorded as an open disagreement, not resolved in our favour.
