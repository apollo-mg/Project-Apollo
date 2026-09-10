# Yes — a 2.42 GiB 4B drives Hermes Agent at 47/61, and every failure is stateful

> **SECOND DEFECT 2026-09-08 01:10:** the 360 s timeout is fixed wall-clock, so the deliberation
> budget scales with decode rate — Spark got **42,480** tokens against Qwen-27B's **9,290**. The
> arms were not given equal thinking room. See `RESULT_HERMESBENCH_WALLCLOCK_BIAS.md`.
>
> **MAJOR CORRECTION 2026-09-07 23:40 — the central claim of this receipt is RETRACTED.**
> Root-causing the failures showed **7 of 14 non-passes are grader blind spots**, not model
> failures: Spark routes tool calls through Hermes' own `tool_search`/`tool_describe`/`tool_call`
> discovery path, and hermesbench's verifiers match by tool name and cannot see through the
> dispatcher. The dispatched calls succeeded and returned correct results. The "every failure is
> stateful" clustering tracks **grader coverage**, not model capability. A corrected score is
> ~54/61 against the 35B's 55-57. See `RESULT_HERMESBENCH_DISPATCHER_BLINDSPOT.md`.

**Date:** 2026-09-07 · **Prereg:** `PREREG_SPARK_HERMES.md` (written before the run, plus a
mid-run sampling amendment — read it, the sampling was off-card)
**Model:** `Spark-X2.5-4B-Q4_K_M`, **2.42 GiB**, arch `spark2_5`
**Engine:** `XHToken/llama.cpp` `4a3635c32`, gfx1201, `-ngl 99 -c 65536 -np 1 -fa on`
**Harness:** `hermesbench run --all --toolsets all --timeout-overhead 300`, 61 tasks, 29 tool schemas
**Raw:** `spark4b_det01/`, `spark4b_det01.log`

## Result

| run | model | GiB | passed | failed | infra | valid pass rate |
|---|---|---:|---:|---:|---:|---:|
| `v5_det02` | Hermes3.6-35B-A3B-Genesis-V5-APEX | ~22 | 55 | 5 | 1 | 0.917 |
| `v5_det03` | " | ~22 | **57** | 4 | 0 | 0.934 |
| `v6_det01` | Hermes3.6-35B-A3B-Genesis-V6-APEX | ~22 | 56 | 5 | 0 | 0.918 |
| **`spark4b_det01`** | **Spark-X2.5-4B-Q4_K_M** | **2.42** | **47** | 12 | 2 | **0.797** |

**It drives the agent.** 47 of 61 real agentic tasks with 29 tool schemas loaded and ~13k-token
first turns, on a 2.42 GiB model on a consumer GPU, 36.4 minutes wall.

The baseline rows are **orientation, not a control** (`AFM-30`): different vendor, size class,
serving stack and node. Nothing here supports "a 4B matches a 35B."

## Every failure is stateful, and that is the finding

| toolset | outcome |
|---|---|
| `t06_process_mgmt` — list, kill, poll | **3 / 3 FAIL** |
| `t07_todo_plan` — plan, update, replan | **3 / 3 FAIL** |
| `t10_memory_facts` — save, recall | **2 / 2 FAIL** |
| `t12_real_world` — error_recovery | FAIL |
| `t02_file_read` — read_missing | FAIL |
| `t08_execute_code` — pandas | FAIL |
| `t13_humaneval_micro` — 2 | FAIL |
| `t02_file_read` — read_paginated | INFRA_ERROR (runaway) |
| `t03_patch_edit` — v4a | INFRA_ERROR (runaway) |
| terminal smoke ×5, file read (4 of 6), patch edit (4 of 5), and the rest | PASS |

Three complete toolsets fail while neighbours pass completely. All three require **carrying
state across turns**: tracking processes, maintaining a plan, persisting and recalling facts.
Single-shot tool use is solid; the model loses the thread the moment the task depends on what
happened three turns ago.

`RESULT_SPARK4B_TOOLS.md` measured 24/24 on tool *mechanics* — parallel calls, chained calls,
even a 4-turn shopping list. That 4-turn state test passed and these fail, which locates the
boundary: short bounded state works, open-ended state under a 29-schema prompt does not.

## The two INFRA_ERRORs are runaways, not infrastructure

Both are timeouts caused by the model generating without terminating. Observed live:
**23,323 tokens** on one turn and **32,097** on another, at 90–97 t/s — four to six minutes of
thinking on a single agent step. Spark's template auto-opens `<think>` on every turn and there
is no non-thinking mode exposed.

This is `RESULT_SEARCH_ASYMMETRY.md` in an agentic setting: deliberation is a search, and
`read_paginated` and `patch_edit_v4a` are tasks where it does not converge. Same shape as the
`xhigh` runaways on `tier_cal`, different corpus.

## Prediction scoring

| # | prediction | conf | outcome |
|---|---|---:|---|
| H-1 | completes the suite without infra errors | 0.65 | **PARTIAL** — completed all 61, but 2 infra errors |
| H-2 | ≥ 30 / 61 passed | 0.55 | **HIT** — 47 |
| H-3 | < 55 / 61 | 0.85 | **HIT** — 47 |
| H-4 | failures concentrate in multi-step/stateful tasks | 0.60 | **HIT**, and more cleanly than predicted — three entire toolsets, no partial credit |
| H-5 | wall-clock well under the P100 baseline's | 0.80 | **UNSCORABLE** — baseline wall time was not recorded in the summaries |

## On the OBS window

The operator launched OBS mid-run, raising GPU contention as a possible confound for the
timeouts. Two observations argue against it mattering:

1. The third infra error landed at **19:54**, after OBS was gone, and the first runaway was
   already in progress before it was mentioned.
2. **The failures cluster by toolset, not by time.** Random GPU interference does not
   selectively remove `process_mgmt`, `todo_plan` and `memory_facts` while leaving their
   neighbours intact.

Recorded rather than dismissed. A retry of the two infra-error tasks in a known-clean state
would settle it and has not been run.

## Sampling — CORRECTED 2026-09-07 23:20: this run WAS on-card

An earlier version of this receipt carried a caveat saying the run used `top_k=20` (Qwen's
value), by analogy with `RESULT_SPARK4B_TIERCAL.md`. **That was wrong.** Verified from the
artifact and the live server:

    Spark-X2.5-4B GGUF:  general.sampling.top_k = -1, top_p = 0.95, temp = 1.0
    Spark-X2.5 card:                       top_k = -1, top_p = 0.95, temp = 1.0

`hermesbench` defines a `SamplingConfig` in `types.py` (temp 0.0, top_p 1.0, top_k -1) but
**no code consuming it was found**, and it sends no sampling in its requests. So llama-server's
defaults apply — and llama-server reads those from `general.sampling.*` in the GGUF. Each model
therefore ran at **its own declared card sampling**.

The same holds for the Qwen comparison run: `Qwen3.8-27B-AD-IQ3_XXS` declares
`top_k = 20, top_p = 0.95, temp = 1.0`, and `/props` on the live server confirms those values.
Both runs are on-card and mutually comparable.

**One deviation in both:** `min_p = 0.05`, llama.cpp's own default. Neither GGUF declares
`min_p` and both cards specify `0.0`.

**The irony worth recording:** `run_fixture.py`, which sets sampling *explicitly* and carefully,
is the harness that got it wrong — it overrode the GGUF's correct values with another model's.
`hermesbench`, which sets nothing, got it right by deferring to the artifact's own metadata.
Explicit configuration is only safer than a default when the explicit value is checked against
the model in hand.

## Limits

One run, one draw. `agent-benchmark-determinism` documents that temp-0 runs on this fleet are
not reproducible and that a single run is an existence proof, not a rate — and this run is at
temperature 1.0, so run-to-run variance should be assumed larger, not smaller. The baseline
itself spans 55–57 across three draws.
