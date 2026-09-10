# A6 answered from data already on disk: the knob is `reasoning_effort`, not `presence_penalty` — and `xhigh` is worse than `medium` on every axis measured

**Date:** 2026-09-07 (analysis) · **Data collected:** 2026-08-21 by `run_card_repeats.sh`
**Node:** `.194`, Qwen3.8-27B Q6_K, `:8080` · **Raw:** `card_{medium,xhigh}_rep{1,2,3}.jsonl`, `card_run.log`
**Status:** RESULT. Closes A6 as posed; bears on A5's cost model (units differ — see below); supports C1.

## What A6 asked, and why it was mis-aimed

A6 asked whether `presence_penalty` collapses the abstention oscillation seen on `CAL-U5`
(32× `UNKNOWN`, 28 repeated 12-word shingles, then a confabulated `1136`). The citation was
sound — Qwen's Best Practices, mirrored on three cards in `data/model_cards/`, does say
*"you can adjust the `presence_penalty` parameter between 0 and 2 to reduce endless
repetition"*. But the parameter was never the live variable:

- The card's **thinking-mode** recommendation is `presence_penalty=0.0`, which is what the
  fixture's `card` preset already uses (`run_fixture.py:112-114`). No deviation existed.
- `presence_penalty=1.5` belongs to the **non-thinking** bundle, with `temperature=0.7` and
  `top_p=0.80`. Lifting one number out of that bundle into a thinking run is off-card twice.
- The real deviation was **temperature**: every run cited in A6 used greedy `temperature=0,
  top_k=1`.

**No new run was needed.** `run_card_repeats.sh` had already executed both effort levels at
the card's published thinking sampling, 3 reps each, on 2026-08-21. The answer was on disk
for seventeen days.

## Result — tier_cal calibration arm, card sampling, 3 reps (24 items per arm)

`temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0`, seeds 1001-1003.
Both effort levels from the same script, same server, same session.

| | `xhigh` | `medium` |
|---|---:|---:|
| answerable ANSWERED-CORRECT | 24/24 | 24/24 |
| unanswerable ABSTAINED | 13/24 | **21/24** |
| unanswerable ANSWERED-WRONG (confabulation) | 6/24 | **3/24** |
| unanswerable NO-STOP/REC | **5/24** | **0/24** |
| unanswerable **chars** median | 5,829 | **1,052** |
| unanswerable **chars** max | 24,062 | **2,005** |
| unanswerable **chars** total | 196,127 | **28,386** |
| answerable **chars** median | 614 | 407 |
| unanswerable items failing ≥1 rep | 5 — U2, U3, U4, U5, U8 | **1 — U3** |

`medium` is better on **every** axis: half the confabulation, no non-termination at all,
**6.9× cheaper** on the unanswerable arm (in characters), failure concentrated from five items to one — and
it gives up nothing on the answerable arm, which is 24/24 either way.

## The claim this falsifies

`RETRACTION_NO_STOP.md` and `CARD_CROSSCHECK.md` both attributed the NO-STOP signature to
greedy decoding, with the reasonable caveat that nothing had separated sampling from model
behaviour. **Sampling was not the cause.** At the model's own published sampling, `xhigh`
still produces 5/24 NO-STOP. Moving to `medium` at that same sampling produces 0/24.

Greedy made it worse; effort is what determines whether it happens at all.

## The claim this supports, with a caveat about the card

The Qwen3.8 card warns that lower reasoning effort *"can lead to insufficient analysis, more
failures, and repeated retries."* On this arm the opposite holds: **more effort produced more
confabulation on false-premise items** (6 vs 3) and every non-termination. Concluding
"no such thing exists" requires *exhausting* a search; more deliberation supplies more
material to mistake for a hit. The card's warning is framed around multi-turn agentic tasks,
which this is not — but it should not be quoted as if it generalises to abstention.

This is the first direct evidence for C1's "medium is the sweet spot" hypothesis on a
non-greedy run.

## Bearing on A5's cost model — suggestive, but the units do not match

**These runs record characters, not tokens.** `run_fixture.py:216` appends
`len(content) + len(reasoning)` to `attempts`, and `ask.last_cost` was empty in the 08-21
rows, so no token count exists in this data. Every figure in the table above is characters.

`RESULT_DRYRUN_03_AND_A5.md` measured its **8.26× median / 11.09× mean** ratio in *tokens*
(answerable median 174 tok, unanswerable 1441) and sized A1 at ~338k completion tokens.
The corresponding character ratios here are:

| | chars, unanswerable total / answerable total |
|---|---:|
| xhigh | 13.8× |
| **medium** | **2.6×** |

**These are not directly comparable to A5's token ratio.** Characters-per-token is not
guaranteed constant across the two arms — an unanswerable reply that oscillates on a short
repeated shingle may have a different ratio from answerable prose, which is precisely the
behaviour under study. The direction (medium far cheaper) is robust; the magnitude is not
transferable to A5's token budget without re-measuring.

**What A1 sizing actually needs:** a run that records `usage` from the server. That is a
harness change, and changing the instrument mid-campaign costs comparability with the 08-21
arms — so it should be a separate, explicitly-labelled run rather than a patch to this one.

## Limits

- **n=3 reps, 8 items per arm.** This is the v0 *gate*, not the A1 measurement corpus; A1
  exists precisely because 16 items cannot detect a small change. A 6-vs-3 confabulation
  difference on 24 trials is suggestive, not established.
- One node, one quant (`.194`/Q6_K). `CAL-U5` did not reproduce its greedy failure at all on
  `AD-IQ3_XXS`/RDNA4, so quant sensitivity is documented and unquantified.
- `low` was not run at card sampling. The ladder has a missing rung.
- No `presence_penalty` arm was run. It remains untested — this receipt says it was the wrong
  first question, not that it does nothing.
