# Fix for the hermesbench version skew: one new module, one changed line, 6 tasks recovered per run, zero regressions

**Date:** 2026-09-08 · **Repo:** `~/projects/hermes-bench-tool-call` (`am423/hermes-bench-tool-call`)
**Fix:** `hermesbench/toolcalls.py` (new, 108 lines) + 5 lines in `hermesbench/runner.py`
**Saved:** `hermesbench_fix/toolcalls.py`, `hermesbench_fix/runner.patch`

## The defect

`RESULT_HERMESBENCH_VERSION_SKEW.md`: hermes-agent `e16ad33a9d` (2026-08-29) moved 19 core
tools **behind the discovery bridge by default** and **renamed** several (`process` →
`process_manage`, `todo` → `todo_list`, `cronjob` → `cronjob_manage`). The bench's last commit
is 2026-06-23 and it is current with its origin — nobody has updated it.

Verifiers match a tool by literal name at the top level of an assistant message. After the
change, a correct agent's calls arrive as
`tool_call{name: "process_manage", arguments: {...}}` and are invisible. Measured: **7 of 14
non-passes** in one run and **6 of 9** in another were correct tool use graded as absent —
including *"expected ≥2 todo calls (replan), got 0"* against two successful calls.

## The fix

Rather than edit 14 verifiers, normalise the trace **once** at the single point where the
runner hands it to the verifier (`_run_verifier`, `runner.py:420`):

```python
from hermesbench.toolcalls import normalise_trace
trace = normalise_trace(read_trace(trace_path)) if trace_path.exists() else []
```

`normalise_trace` unwraps `tool_call{name, arguments}` into a top-level call and maps renamed
tools back to the legacy names the verifiers already use, re-emitting `arguments` as a JSON
string (which is what they already parse). **Every existing verifier works unmodified against
both pre- and post-2026-08-29 agents.**

`toolcalls.py` also exports `iter_tool_calls`, `used_tool` and `count_tool` for new verifiers
that would rather not hand-roll the scan.

## Validation — full trace sets, two models, real verifiers

Each task's actual `verifier.py` was executed twice, on the raw trace and the normalised one:

| run | recovered (FAIL→PASS) | regressions (PASS→FAIL) | unchanged |
|---|---:|---:|---:|
| `spark4b_det01` (Spark-X2.5-4B) | **6** | **0** | 55 |
| `qwen38_deploy_det02` (Qwen3.8-27B) | **6** | **0** | 55 |

Recovered in both: `t06_process_mgmt` ×3, `t07_todo_plan` ×3. Not recovered:
`t10_memory_facts/t03_avoid_dup`, which made no dispatcher calls and looks like a genuine
failure.

## Corrected scores

| run | as measured | with the fix |
|---|---:|---:|
| Spark-X2.5-4B Q4_K_M (2.42 GiB) | 47/61 | **53/61** |
| Qwen3.8-27B AD-IQ3_XXS deploy, 32k | 44/60 | **50/60** |
| *Hermes3.6-35B-A3B baseline (2026-07-28)* | *55–57/61* | *unaffected — ran pre-rename* |

The baseline was measured against the old tool surface, so it needs no correction. That makes
Spark's **53/61** and the 35B's **55–57/61** a genuinely close comparison — the first one in
this campaign that is apples-to-apples on tool visibility.

**Still not corrected for:** the fixed wall-clock timeout, which grants a 118 t/s model 42,480
generated tokens and a 25.8 t/s model 9,290 (`RESULT_HERMESBENCH_WALLCLOCK_BIAS.md`). That
remains an open confound in any cross-model comparison here.

## Suitable for upstream

The change is additive and behaviour-preserving for pre-rename traces: a trace with no
`tool_call` wrappers and no renamed tools passes through untouched, which is why 55 verdicts
are unchanged in each run. Offered to the maintainer along with the skew report.

## Limits

Validated on two runs from two models on one node. The alias map covers the five tools named in
`e16ad33a9d`; any later rename needs adding. A malformed dispatch (`tool_call` with no `name`)
is passed through rather than dropped, so it still fails — deliberately, since that is a real
agent error rather than a grader artifact.
