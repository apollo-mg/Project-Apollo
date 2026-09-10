# Correcting the sampling drops Spark's abstention 18/24 → 12/24, and moves nothing else

**Date:** 2026-09-07, 21:03 · **Model:** `Spark-X2.5-4B-Q4_K_M`, 2.42 GiB
**Node:** RX 9070 XT · `XHToken/llama.cpp` `4a3635c32`, `-ngl 99 -c 8192 -np 1 -fa on`
**Harness:** `run_fixture_structfix.py --sampling spark_card` (new preset), seeds 1001–1003
**Raw:** `sparkcard_rep{1,2,3}.jsonl`, `spark_card.log`

`RESULT_SPARK4B_TIERCAL.md` was run at `top_k=20` — **Qwen3.8's** card value, inherited from
`run_fixture.py`'s hardcoded `card` preset and reused on a non-Qwen model without checking.
Spark-X2.5's card specifies `temperature=1.0, top_p=0.95, top_k=-1`. This is the same fixture,
same seeds, same everything, at the model's own recommended sampling.

## Result

| | Qwen's card (`top_k=20`) | **Spark's own card (`top_k=-1`)** | Δ |
|---|---:|---:|---:|
| answerable ANSWERED-CORRECT | 18/24 | **18/24** | **0** |
| unanswerable ABSTAINED | **18/24** | **12/24** | **−6** |
| unanswerable ANSWERED-WRONG | 4 | 6 | +2 |
| NO-STOP | 2 | 2 | 0 |
| unanswerable chars median | 2,731 | 2,016 | −715 |

Answerable failures are **the same items in both arms** — `CAL-A6` (3/3), `CAL-A1`, `CAL-A5`.
`CAL-U3` abstains 3/3 under both.

## The change is confined to the abstention channel, which is the predicted signature

With `top_p=0.95` already applied, `top_k=20` binds **only where the nucleus admits more than
20 tokens** — high-entropy positions. Factual recall on the answerable arm is low-entropy: the
model either has the fact or does not, and top-k never binds there. The abstain-or-answer
decision on an unanswerable item is exactly the high-entropy case.

So the prediction was that correcting `top_k` should move abstention and leave knowledge alone.
**It moved abstention by 6 and knowledge by 0**, with identical items failing on the answerable
arm. The mechanism reading is confirmed by the shape of the change, not just its direction.

Practical consequence: `top_k=20` **suppressed the model's tendency to answer** in precisely
the positions the metric measures. The earlier 18/24 was an artifact of the wrong setting.

## What this retracts

`RESULT_SPARK4B_TIERCAL.md` triggered prereg item **S-4** — *"if S-2 holds and S-3 fails,
abstention is not a Qwen-specific property"* — on the strength of 18/24 against Qwen3.8-27B's
21/24, a near-match.

**The correct-sampling comparison is 12/24 against 21/24.** That is a large gap, not a near
match, and S-4 is **withdrawn as stated**. The narrower claim that survives:

> A 2.42 GiB non-Qwen model reaches 12/24 abstention with 18/24 answerable at its own
> recommended sampling. That is materially worse calibration than Qwen3.8-27B, and materially
> better than nothing — but it does not establish that abstention of Qwen's quality exists
> outside Qwen.

The confound named in `RESULT_SPARK4B_TIERCAL.md` still applies on top of this: at 18/24
answerable, some of Spark's abstention is thin knowledge rather than calibration, and this
fixture cannot separate them without A1's hard-answerable arm.

## What is NOT affected

`RESULT_SPARK4B_TOOLS.md` (24/24) and `RESULT_SPARK4B_STRUCT.md` (18/18) are **ceilings** — a
sampling change can only move them down, and both were perfect. The qualitative claims survive:
it makes parallel tool calls, chains on returned values, declines to invent a missing argument.
Re-running them at `top_k=-1` would tighten the numbers but cannot overturn "it can do this".

`RESULT_SPARK4B_HERMES.md` (47/61) — **corrected 23:20: that run was on-card after all.**
`hermesbench` sends no sampling, so llama-server's GGUF-derived defaults applied, and the Spark
GGUF declares `general.sampling.top_k = -1` matching its card. Only the `tier_cal`, tool and
struct arms went through `run_fixture.py`'s explicit override. 47/61 stands as an on-card
number.

## Method note

The preset is now `spark_card` in `run_fixture_structfix.py`, alongside a comment recording
why: *a preset named for a document is only that document for the model it was written for*.
`run_fixture.py` remains untouched so every historical run stays reproducible against the
instrument that produced it.

## Limits

8 items per arm × 3 reps. A 6-point move on 24 trials is larger than the noise seen elsewhere
in this campaign (the medium/low arms differed by 0), but this is still gate-sized data.
One model, one quant, one node.
