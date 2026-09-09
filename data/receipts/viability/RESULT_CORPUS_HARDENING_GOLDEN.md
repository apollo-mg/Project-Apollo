# RESULT: golden-trace replay — the harness now tests itself

**Date:** 2026-09-08
**Repo:** `~/projects/hermes-bench-tool-call`
**Added:** `tests/test_golden_traces.py`, `tests/support/seed_golden.py`, `tests/golden/` (14 fixtures)

## The problem this closes

hermes-agent `e16ad33a9d` (2026-08-29) renamed core tools and deferred 19 more behind the
`tool_search`/`tool_describe`/`tool_call` discovery bridge. A **correct** agent then read as having
made no tool calls, and six tasks in `t06_process_mgmt` / `t07_todo_plan` scored FAIL.

The existing 122-test suite stayed **entirely green** through all of it. Nothing replayed a real
trace through a real verifier, so no test could see the seam where the harness broke. The bug was
found by hand, by re-scoring traces offline, after burning GPU hours on runs whose scores were wrong.

## What was added

A golden fixture is a frozen `(task, worktree, trace)` triple plus the verdict a human confirmed.
`tests/test_golden_traces.py` replays each through the **real** grading path — `_run_verifier`,
including `normalise_trace` — and asserts the verdict. No GPU, no model, no network.

**Runtime: 0.14 s for 31 tests.** The bug that cost hours of P100 time is now caught before the
kettle boils.

Seeded 14 fixtures from `qwen38_fixed_grader`, including **all six** tasks the rename broke
(`seed_golden.py` gives the dispatcher-exposed families full coverage and one representative task
elsewhere).

### Tests

| test | what it defends |
|---|---|
| `test_golden_trace_replays_to_expected_verdict` | a confirmed run must keep grading the same way |
| `test_empty_run_does_not_pass` | **negative control** — empty worktree + empty trace must never PASS |
| `test_renamed_tools_are_still_recognised` | names the rename regression directly |
| `test_discovery_bridge_calls_are_unwrapped` | names the bridge regression directly |
| `test_golden_suite_is_not_empty` | a suite that seeds zero fixtures stays green and proves nothing |

The negative control matters: a suite of only-should-pass fixtures is satisfied by a verifier that
unconditionally returns PASS. It empties the **worktree** as well as the trace, because several
verifiers correctly grade world state rather than the trace (AFM-33), so an empty trace alone can
legitimately still pass.

## Validation — the suite was mutation-tested, not merely observed green

A suite green on its first run proves nothing until it is shown capable of going red
(`readiness-probes-lie`). Three mutations, each restored byte-identical afterwards:

| mutation | result |
|---|---|
| `_ALIASES = {}` | **7 failed** — the 6 t06/t07 tasks + the rename unit test |
| disable the `tool_call` unwrap | **7 failed** — the same 6 + the bridge unit test |
| `normalise_trace` → `return trace` (the exact pre-fix state) | **8 failed** — the 6 + both unit tests |

Both halves of the fix are independently load-bearing: these traces call
`tool_call(name="process_manage")`, so grading them needs the unwrap **and** the alias.

**A methodology note worth keeping:** the first attempt at mutation 1 silently failed to apply — the
regex did not match the real multi-line `_ALIASES` — and the suite ran green. That green was
meaningless, and reads exactly like a passing mutation test. *Always assert that a mutation actually
landed before interpreting the result.* Same family as AFM-34.

## Full-suite status

`122 passed, 1 failed`. The single failure is pre-existing and unrelated
(`test_statsd_sources.py::test_gpu_sample_shape`): hermesbench's statsd GPU source returns no
`util_pct` on `amdgpu`, only `vendor/name/temp_c/power_w`, and samples `card1`.

**This is not cosmetic.** This session's timeout wall came down to GPU throughput, and the bench's
own telemetry cannot observe GPU utilization on the AMD control plane. Logged as a follow-up.

## Remaining corpus work (agreed 2026-09-08, not yet done)

1. **Grade outcomes, not routes** (AFM-33) — check world state, not which tool name appeared.
   Immune to renames *and* to different-valid-routes. Would have prevented this bug outright.
2. **Budget timeouts in tokens, not wall-clock.** A 360 s wall-clock cap makes the score depend on
   server uptime — see `PREREG_TIMEOUT_WALL.md`. Floor of ~7.5k per A5 (`CAL-U5` needed 7109).
3. **Split the verdict schema.** PASS/FAIL/INFRA_ERROR collapses genuine failure, route mismatch and
   grader-cannot-parse into one bucket. We cannot measure what we cannot distinguish.
4. **`util_pct` on amdgpu** in the statsd source.
