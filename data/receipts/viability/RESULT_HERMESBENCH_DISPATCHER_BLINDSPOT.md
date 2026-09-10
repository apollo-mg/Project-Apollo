# hermesbench cannot see tool calls made through Hermes' own `tool_call` dispatcher — 7 of Spark's 14 non-passes are grader blind spots

> **ROOT CAUSE FOUND 2026-09-08 — this receipt describes the symptom, not the cause.**
> hermes-agent `e16ad33a9d` (2026-08-29) **renamed** the tools (`process`→`process_manage`,
> `todo`→`todo_list`) and **deferred 19 core tools behind the discovery bridge by default**.
> The bench (last commit 2026-06-23) still checks pre-rename names. Models are not *choosing*
> discovery — it is the only path available. The 35B baseline passed because it ran 2026-07-28,
> a month before the change. **No cross-run comparison in this campaign is valid.**
> See `RESULT_HERMESBENCH_VERSION_SKEW.md`.

**Date:** 2026-09-07 23:40 · Found by root-causing `RESULT_SPARK4B_HERMES.md`'s failures
**Traces:** `/home/mark/projects/hermes-bench-tool-call/traces/{spark4b_det01,v5_det03}/`

## The defect

`hermesbench`'s verifiers check for a tool call **by tool name at the top level** of the
assistant message. Hermes exposes a progressive-discovery path for large tool sets —
`tool_search` → `tool_describe` → `tool_call{name, arguments}` — and a call routed that way is
invisible to the check.

With **29 tool schemas** loaded, discovery-before-calling is arguably the correct strategy.
The grader scores it as not using the tool at all.

## Evidence — same tasks, two models, two call styles

| task | `Hermes3.6-35B-A3B` (v5_det03) | `Spark-X2.5-4B` (spark4b_det01) |
|---|---|---|
| `t06_process_mgmt/t01_list` | `process` | `tool_describe` → **`tool_call{process_manage, {action:"list"}}`** |
| `t07_todo_plan/t01_plan` | `todo` | `tool_search` → `tool_describe` → **`tool_call{todo_list, {todos:[4]}}`** |
| `t10_memory_facts/t01_save` | `memory` | `memory` (direct, different arg shape) |

The baseline calls directly and passes. Spark discovers and is failed.

**The dispatched calls succeeded and returned real results:**

```
t06 list    tool_call -> {"processes": []}                 (correct — nothing was running)
t07 plan    tool_call -> {"todos":[t1,t2,t3,t4]}           (4 items, exactly what was asked)
t07 replan  tool_call -> {"todos":[...]}  x2               (grader: "expected >=2 ... got 0")
```

`t07_todo_plan/t03_replan` is the clearest case: the criterion is *"expected >=2 todo calls
(replan), got 0"*. The model made **two**, both returning todo lists.

## CONFIRMED ON A SECOND MODEL 2026-09-08 09:20 — not a small-model quirk

`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` (deployment config, `qwen38_deploy_det02`) hits the identical
blind spot:

```
t06_process_mgmt/t01_list   tool_describe → tool_call{process_manage}   graded "did not use process(action='list')"
t06_process_mgmt/t02_kill   terminal      → tool_call{process_manage}   graded "did not use process(action='kill')"
```

Two models, two vendors, two size classes (2.42 GiB and 9.73 GiB), both routing through
Hermes' own `tool_search`/`tool_describe`/`tool_call` discovery path. Both scored as not using
the tool.

The 35B-A3B baseline remains the only model measured that calls directly — which is why the
defect never surfaced against it. This is now **a property of the grader**, not of any one
model, and any hermesbench score for a model that prefers discovery is an undercount by an
amount that depends on how often it chooses that path.

## A second, independent blind spot: argument shape

`t10_memory_facts/t01_save` — verifier: *"model did not use memory(action='add')"*. The model
called `memory` **directly**, and the tool accepted and applied it:

```json
call: {"target":"memory","operations":[{"action":"add","content":"…blue-swan-42"}]}
resp: {"success":true,"done":true,"entry_count":1,"message":"Applied 1 operation(s)."}
```

`action: "add"` is present, nested inside `operations[]` — which is the tool's own schema. The
verifier looks for `action` at the top level. **The tool executed the request and the grader
failed it.**

## Scope

| Spark non-pass | grader reason | actually |
|---|---|---|
| `t06_process_mgmt/t01_list` | did not use process(action='list') | dispatched `process_manage{action:list}` ✓ |
| `t06_process_mgmt/t02_kill` | did not use process(action='kill') | dispatched `process_manage` ✓ |
| `t06_process_mgmt/t03_poll` | did not use process | dispatched `process_manage` ✓ |
| `t07_todo_plan/t01_plan` | did not create a 4-item todo list | dispatched `todo_list`, 4 items ✓ |
| `t07_todo_plan/t02_update` | did not use todo | dispatched `todo_list` ×3 ✓ |
| `t07_todo_plan/t03_replan` | expected ≥2 todo calls, got 0 | dispatched `todo_list` ×2 ✓ |
| `t10_memory_facts/t01_save` | did not use memory(action='add') | called `memory` directly, tool applied it ✓ |
| `t02_file_read/t04_read_missing` | did not attempt the missing file | not investigated |
| `t08_execute_code/t02_pandas` | did not use execute_code | no dispatch; searched for `data.csv`, used terminal |
| `t10_memory_facts/t02_recall` | did not use memory | **0 tool calls — looks genuine** |
| `t12_real_world/t02_error_recovery` | did not recover from missing file | not investigated |
| `t13_humaneval_micro/humaneval_2` | Python traceback | genuine code failure |
| `t02_file_read/t03_read_paginated` | INFRA_ERROR (timeout) | runaway, genuine |
| `t03_patch_edit/t05_v4a` | INFRA_ERROR (timeout) | runaway, genuine |

**7 of 14 non-passes are grader blind spots.** A corrected score would be about **54/61**
against the 35B baseline's 55–57 — near parity, not the 8–10 point gap reported.

**That corrected number is an inference, not a measurement.** It assumes the verifier's own
stated criterion ("did the model use tool X") would pass once the dispatcher is followed. A
real re-grade needs the verifier taught to unwrap `tool_call`, then a re-run.

## What this retracts from `RESULT_SPARK4B_HERMES.md`

That receipt's central claim was:

> *Every failure is stateful… the model loses the thread the moment the task depends on what
> happened three turns ago.*

**Wrong, twice.** The three "stateful" toolsets (`process_mgmt`, `todo_plan`, `memory_facts`)
are precisely the ones the model handled through the dispatcher, and `t10_.../t01_save` is
turn one — there is nothing to remember yet. The clustering that looked like a capacity limit
was a clustering of **grader coverage**.

I also argued the toolset clustering was evidence *against* the OBS confound. That argument
was right for the wrong reason: the clustering is real, but it tracks the grader, not the GPU.

## Why the pattern is worth naming

This is the **third** harness defect found today that penalises correct model behaviour:

1. `AFM-31` — `tier_struct` sent jointly-unsatisfiable instructions; a literal-minded model
   scored 2/6 VOID, then 18/18 once fixed.
2. `A4` / `RESULT_IQ3_GLIMPSE_MEDIUM.md` — exact-match grading failed `weber (Wb)` against
   gold `weber`.
3. This — call-presence-by-name cannot see a dispatcher, and argument checks assume one shape.

In all three the model did the right thing and the instrument recorded a failure. In all three
the defect was invisible until a model that behaved *differently but correctly* hit it — Qwen
resolved the contradiction, called tools directly, and answered in bare units, so it passed and
the defects stayed hidden.

**Rule:** when a model fails a capability the vendor claims and the failure clusters by
subsystem, read the trace before believing the score. A grader measures the behaviour it was
written to expect, which is not the same as the behaviour that is correct.

## For TheTom

Two concrete fixes, both small:

1. **Unwrap `tool_call`** when checking tool usage — resolve `arguments.name` to the underlying
   tool before matching. Six tasks in this run alone.
2. **Match arguments semantically, not positionally** — `memory(operations=[{action:'add'}])`
   satisfies "used memory with action add". The tool's own schema is the authority; it accepted
   the call.

Offer: we can re-run the suite after either fix and report the delta on 2×P100 and RDNA4.
