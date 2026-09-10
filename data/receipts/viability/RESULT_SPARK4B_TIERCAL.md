# A 2.42 GiB non-Qwen 4B holds 75% abstention — but the fixture cannot separate calibration from ignorance

> **SUPERSEDED IN PART, 2026-09-07 21:03.** This run used `top_k=20` (Qwen3.8's card value).
> At Spark's own card (`top_k=-1`), abstention is **12/24, not 18/24**, with the answerable arm
> unchanged at 18/24. Prereg item **S-4 is withdrawn**. See `RESULT_SPARK4B_CORRECT_SAMPLING.md`.

**Date:** 2026-09-07 · **Prereg:** `PREREG_SPARK4B.md` (written before the run)
**Model:** `XHToken/Spark-X2.5-4B-GGUF`, `Q4_K_M` 2.42 GiB, arch `spark2_5`
**Engine:** `XHToken/llama.cpp` `4a3635c32` built for **gfx1201** (their README claims CPU+CUDA only)
**Node:** desktop RX 9070 XT · `-ngl 99 -c 8192 -fa on`, `--tier cal --sampling card`, seeds 1001–1003
**Raw:** `spark_rep{1,2,3}.jsonl`, `spark_run.log`

First non-Qwen model on `tier_cal`. Every prior calibration number in this corpus is
Qwen3.8-27B.

## Result

| model | GiB | answerable | abstained | confabulated | NO-STOP | unansw chars med |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3.8-27B Q6_K *(other box)* | 21.30 | 24/24 | 21/24 | 3 | 0 | 755 |
| Qwen3.8-27B AD-IQ3_XXS | 11.25 | 24/24 | 23/24 | 1 | 0 | 892 |
| **Spark-X2.5-4B Q4_K_M** | **2.42** | **18/24** | **18/24** | 4 | 2 | 2,731 |

Spark's unanswerable failures: `CAL-U2` ×3, `CAL-U6`, `CAL-U1`, `CAL-U4`.
Its answerable failures are genuine knowledge gaps, not grading artifacts:

```
CAL-A1  'Saskatoon'          (gold 'Regina')     capital of Saskatchewan
CAL-A5  '1428', '1429'       (gold '1494')
CAL-A6  'Wright','Haas','Wright'  (gold 'Williams')   fails 3/3
```

## Prediction scoring

| # | prediction | conf | outcome |
|---|---|---:|---|
| S-1 | HIP build works, model serves on gfx1201 | 0.80 | **HIT** — the fork adds nothing under `ggml/`, so ROCm was never actually blocked |
| S-2 | answerable ≥ 18/24 | 0.65 | **HIT** — exactly 18 |
| S-3 | abstention ≤ 15/24, materially worse than Qwen | 0.60 | **MISS** — 18/24 |
| S-5 | `CAL-U3` confabulated on ≥2 of 3 reps | 0.75 | **MISS** — abstained 3/3 |
| S-4 | *conditional:* if S-2 holds and S-3 fails, abstention is not Qwen-specific | — | **TRIGGERED** |

S-3 was deliberately a bet against the interesting outcome. It lost, which makes the result
worth more than if it had been predicted.

## `CAL-U3` and why it is not the win it looks like

*"In which year did Mendeleev win the Nobel Prize in Chemistry?"* — false premise, all entities
real. It defeated **every** Qwen configuration at high bitrate: `1906` on 10 of 10 runs at Q6_K
across three effort levels, `1907` ×3 at AD-IQ3_S. Spark abstains **3/3**.

**This is confounded and must not be reported as a calibration win.** A model with a strong but
wrong Mendeleev association answers `1906`. A model that barely knows who Mendeleev is abstains
— and scores *correct for the wrong reason*. Spark's answerable arm at 18/24 establishes that
its knowledge is materially thinner than Qwen's, so ignorance is a live explanation for its U3
abstention and this fixture cannot rule it out.

The AD quant ladder makes the point directly: Qwen3.8-27B at **IQ2_XS** also abstains on U3
(`UNKNOWN` ×3) — and it gets there by *losing the retrieval*, with the answerable arm dropping
to 20/24 in the same run (`RESULT_AD_QUANT_LADDER.md`). Thin knowledge produces the same
observable as good calibration.

## What this does and does not establish

**Does:** abstention behaviour of this quality is **not unique to Qwen**. A 2.42 GiB model from
a different vendor, different architecture, different training pipeline, reaches 18/24 on the
unanswerable arm with a non-trivial 18/24 on the answerable arm. Prior to this run every
calibration number in the corpus was one model family.

**Does not:** establish that Spark is *as well calibrated* as Qwen3.8-27B. It is worse on both
arms (18 vs 21–23 abstained, 18 vs 24 answerable), and the gap on the answerable arm means part
of its abstention is unearned. Nor does it separate vendor from size — a 4B and a 27B differ on
both axes at once (`AFM-30`).

**The blind spot this exposes is the same one A1 already names.** Without **hard-but-answerable**
items, "abstains appropriately" and "does not know much" are the same observation. That
amendment was written this afternoon from the AA disagreement; this run reaches it from a
second direction, which is the strongest argument yet that A1's third arm is the binding
constraint on every calibration claim here.

## Incidental findings

- **The XHToken fork builds and runs on ROCm/gfx1201** despite documenting only CPU and CUDA.
  It is 15 commits ahead of upstream `6d0549831`, 541 lines, nothing under `ggml/` — a
  146-line graph builder in `src/models/spark2_5.cpp` using existing ops, notably
  `build_attn_inp_kv_iswa()`. Worth telling them; it costs them nothing and widens their
  hardware base.
- **The template ignores `reasoning_effort`** — verified by rendering `None`/`medium`/`xhigh`,
  all byte-identical. So this arm and Qwen's `medium` arm are both at the no-injected-
  instruction baseline. It does inject a default `"you are a helpful assistant."` where Qwen's
  `medium` injects zero characters; small asymmetry, recorded.
- The template auto-opens `<think>` — always a reasoning model, no non-thinking mode exposed.
- 1M context is native (`context_length 1048576`, **no rope_scaling** in config or GGUF).
  9 full-attention layers of 36, `sliding_window 512` → **~36 KiB/token** f16 KV, roughly half
  Qwen3.8-27B's 64.

## Limits

8 items per arm × 3 reps. One quant, one model, one node. `AFM-30` applies to every
cross-model comparison here.

> **SAMPLING CAVEAT (added 2026-09-07):** this run used `top_k=20`, which is **Qwen3.8's** card value
> inherited from `run_fixture.py`'s hardcoded `card` preset. **Spark-X2.5's card specifies `top_k=-1`.**
> See `PREREG_SPARK_HERMES.md` Amendment for why this bites hardest at high-entropy positions —
> exactly where abstention is decided. Ceiling results (24/24, 18/18) can only move down; the
> `tier_cal` abstention figure is the one that needs re-running.
