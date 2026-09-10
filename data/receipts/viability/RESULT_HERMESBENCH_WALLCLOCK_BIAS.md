# hermesbench's fixed wall-clock timeout converts decode speed into apparent capability

**Date:** 2026-09-08 01:10 · Found while running `Qwen3.8-27B-AD-IQ3_XXS` through the 61-task suite
**Node:** RX 9070 XT · `-c 65536 -np 1 -fa on` · `--timeout-overhead 300`
**Raw:** `qwen38_iq3_det01/`, server log in `spark_raw/`

## The observation

Qwen3.8-27B at IQ3 passed tasks 1–22, then produced **21 consecutive `INFRA_ERROR`s**, every one
at exactly 360 s, spanning six unrelated toolsets (`write_new`, `process_mgmt`, `todo_plan`,
`execute_code`, `web_lookup`, `memory_facts`). A model does not fail every task category
uniformly.

The server was healthy throughout — 25.8 t/s, no errors, GPU nominal. Slot releases land exactly
six minutes apart (124:56, 130:56, 136:56, 143:56). The reason is not a hang:

```
prompt (29 tool schemas):   14,288 tokens
released at:                23,008 tokens   ->  8,720 generated
at 25.8 t/s:                8,720 tokens    =   338 s
timeout:                    360 s
```

**The model generates continuously for the whole window and is cut off mid-thought.**

## The bias

The timeout is fixed wall-clock. The generation budget it implies is therefore
`timeout × decode_rate`, which differs per model by the decode ratio:

| model | GiB | decode | tokens available in 360 s |
|---|---:|---:|---:|
| `Spark-X2.5-4B-Q4_K_M` | 2.42 | 118 t/s | **42,480** |
| `Qwen3.8-27B-AD-IQ3_XXS` | 11.25 | 25.8 t/s | **9,290** |

**Spark received 4.6× the deliberation budget for the identical timeout.** Its own observed
runaways reached 23,323 and 32,097 tokens — comfortably inside its budget, killed only twice.
Qwen cannot reach 10,000 tokens before the wall.

So a slower model is scored as failing tasks it might complete, and the metric partly measures
**tokens per second**, not task competence. `--timeout-overhead 300` was sized against P100
*prefill* (per the comment in `run_v5_det03.sh`: *"P100 prefill ~148 tok/s, 29 tool schemas push
turn 1 to ~13k tokens (~83 s)"*) — generation was never costed.

## Why the earlier comparison is not usable as run

`RESULT_SPARK4B_HERMES.md` reported Spark 47/61 against a 35B-A3B baseline of 55–57/61. Two
separate defects now sit under that comparison:

1. **`RESULT_HERMESBENCH_DISPATCHER_BLINDSPOT.md`** — verifiers cannot see calls routed through
   `tool_call`; 7 of Spark's 14 non-passes were graded wrong.
2. **This** — the timeout budget scales with decode rate, so the arms had different effective
   deliberation limits.

Both push in directions that are model-specific, not random. **No cross-model score from this
harness should be quoted until both are addressed.** The 35B baseline is a 3B-active MoE and
presumably fast, which would place it on the favourable side of (2) as well.

## Interaction with the effort ladder

`RESULT_A6_LOW_RUNG.md` measured `xhigh` producing 5/24 NO-STOP against `medium`'s 0/24, and
6.9× the output. hermesbench sets no `reasoning_effort`, so Qwen runs at its template default of
`xhigh` — the setting most prone to non-termination, on the model with the least headroom.

**`reasoning_effort: medium` is the single highest-value change for this harness.** Our own data
says it costs nothing on calibration (21/24 abstention at both) and cuts output ~7×, which on
this arm is the difference between finishing inside the wall and not.

## Recommended fixes, in order

1. **Budget in tokens, not seconds** — or scale the timeout by measured decode rate. A fixed
   wall clock is a speed benchmark wearing a capability benchmark's clothes.
2. **Set `reasoning_effort: medium`** for models that expose it (or expose the knob per-run).
3. **Report `INFRA_ERROR` separately from `FAIL`** in the headline, and record generated-token
   counts per task so a truncation is visibly distinct from a wrong answer.

## Limits

One model, one node, one timeout value. The decode rates are measured (n=172 samples for Spark;
sustained 25.8–26.0 t/s for Qwen), but the claim that Qwen *would* pass those tasks with a larger
budget is **untested** — it is a bound on what the current data can show, not a prediction. Re-running
Qwen at `--timeout-overhead 900` or at `reasoning_effort: medium` would settle it.
