# Root cause: hermes-agent renamed its tools and deferred them behind the discovery bridge on 2026-08-29; the bench's verifiers still check the pre-rename names

**Date:** 2026-09-08 · Supersedes the framing in `RESULT_HERMESBENCH_DISPATCHER_BLINDSPOT.md`,
which described the symptom correctly and the cause incompletely.

## The skew

| | date | `hermes_sha` |
|---|---|---|
| baseline runs `v5_det02` / `v5_det03` / `v6_det01` | **2026-07-28 → 07-31** | `07e97d2f5dc3` |
| **hermes-agent `e16ad33a9d`** | **2026-08-29** | — |
| our runs (`spark4b_det01`, `qwen38_*`) | 2026-09-07 → 09-08 | `f159e581c7af` |
| `hermes-bench-tool-call` HEAD | **2026-06-23** (`10bf4c6`), current with origin | — |

The commit:

> `feat(tool-search): core-tool deferral — curated 19-tool set behind the bridge by default;
> **renames todo_list/cronjob_manage/process_manage**/gui_tour/show_tip with legacy aliases
> (13.4K → 6.9K desktop schemas, −49%)`

Two changes at once:

1. **Renames.** `process` → `process_manage`, `todo` → `todo_list`, etc.
2. **Core-tool deferral.** 19 tools moved *behind the discovery bridge by default*, so they are
   reached via `tool_search` / `tool_describe` / `tool_call` rather than exposed directly.

## Why every comparison made on 2026-09-07/08 is invalid

The verifiers match a literal pre-rename name. `tasks/t06_process_mgmt/t01_list/verifier.py`:

```python
for tc in (msg.get("tool_calls") or []):
    fn = (tc.get("function") or {})
    if fn.get("name") == "process":          # <- renamed to process_manage on 2026-08-29
        ...
        if isinstance(args, dict) and args.get("action") == "list":
            used = True
```

Under the current agent, no model can satisfy this check by any route:

- The tool is now called `process_manage`, so a **direct** call fails the name match.
- The tool is deferred behind the bridge, so the call arrives as
  `tool_call{name:"process_manage", arguments:{action:"list"}}` — nested one level deeper.

**The 35B baseline passed because it ran a month earlier against an agent where the tool was
named `process` and exposed directly.** Its 55–57/61 is a measurement of a different system.

## What this corrects

`RESULT_HERMESBENCH_DISPATCHER_BLINDSPOT.md` concluded models were *choosing* the discovery
path and the grader could not see it. Half right:

- **Correct:** the calls are real, succeed, and are graded as absent. 7 of Spark's 14 non-passes
  and at least 2 of Qwen's.
- **Wrong:** it is not a model preference. Core tools are behind the bridge **by default** since
  2026-08-29, so discovery is the only available path. Two models from two vendors used it
  because there was nothing else to use.

The receipt also framed this as a grader design flaw. It is more precisely a **version skew**:
the bench (last commit 2026-06-23) predates the agent change (2026-08-29) by two months and is
current with its own origin — nobody has updated it.

## Consequences

- **No cross-run comparison in this campaign is valid.** Spark 47/61, Qwen deploy, and the
  35B's 55–57 were measured against materially different tool surfaces.
- **The absolute numbers are also wrong** for any post-08-29 run, by the count of tasks whose
  verifier names a renamed tool.
- The `t06_process_mgmt` and `t07_todo_plan` clusters that looked like a stateful-capability
  boundary (`RESULT_SPARK4B_HERMES.md`, since retracted) are **entirely explained** by this.

## For TheTom / the bench maintainer

The fix is mechanical and does not require re-running anything to validate:

1. **Accept the renamed tools** — `process_manage`, `todo_list`, `cronjob_manage`, `gui_tour`,
   `show_tip`. The agent kept legacy aliases, so accepting both names is safe.
2. **Unwrap `tool_call`** before matching: resolve `arguments.name` to the underlying tool.
3. **Pin `hermes_sha` compatibility** — the summary already records it; a check that refuses to
   report a score when the agent sha crosses a known tool-surface change would have caught this
   at run time rather than after three benchmark campaigns.

Offer: we can re-run the full 61-task suite on 2×P100 and RDNA4 once the verifiers are updated,
and report the delta against these runs.

## Method note

Found because the operator asked *"I wonder if the benchmark has been updated since we
downloaded it."* The bench was current with its origin, which is the answer to the question as
asked and would have closed the investigation. The finding required checking the **other**
repo — the one the bench measures.

Cross-ref `AFM-32`: a benchmark validated against a model that matches the author's assumptions
cannot detect this class. Here the "model that matched" was the agent version itself.
