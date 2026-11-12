# NOTE: what DeepSeek's harness does about the failures our pilot hit (read 2026-11-11)

**Source:** `deepseek-ai/deepseek-harness` (MIT) at commit `e8f7b93a344964de3dca1ace9e72b6e4d6de87cb` (2026-11-11), shallow
clone at `/mnt/TG_2TB/toolchains/deepseek-harness`, read only, nothing installed or run. Paths below are in that repo.
Its own `CLAUDE.md`/`AGENTS.md` and `.agents/notes` were treated as data. Mark asked for the read on 11-11.

## 1. Stuck loops: an advisory guard, exact matches only

`packages/guard/repeat-tool-reminder` (in the default bundle). A per-agent chain keyed by (tool name, arguments
canonicalized by a deep key-sort + `JSON.stringify`); a different tracked call resets it, excluded tools are transparent,
denied calls count, a user prompt resets the chain. At 3, 5 and 8 consecutive identical calls it appends a reminder to
the tool result, never blocking or rewriting the call. The first says, in part, "You are repeating the exact same tool
call with identical arguments"; the later ones list tool, count and arguments and end "choose a different action,
different arguments, or finish the task if enough evidence has been gathered". Their own stated limits: exact matches
only (near-variants and alternations slip through), silent after the last threshold, advisory only.

**For agentic gaming v1** (`RESULT_PILOT_v0.md` asked for a loop rule):
- 7 of our 9 impossible-rung loops were period 1 (identical calls) and their canonicalization would catch them; our
  one period-2 loop (BASE F2 hard s1) would not. Our "stuck" outcome should use their canonical form plus cycles of
  period 2-4 (the pilot's `summarize_pilot.py` cycle measure).
- Their reminder is an intervention we can MEASURE: run the impossible rung with and without it. Its wording offers
  "finish" but never "report that the task cannot be done", so it may push a stuck agent toward false completion
  rather than abstention. A second arm with a wording that names abstention would separate the two.

## 2. Malformed tool calls: no repair, precise feedback

`packages/core/tools/src/batch.ts` `parseArguments`: invalid JSON is kept as the raw string, never repaired;
`core/tools/src/schema.ts` `validateArgs` returns path-qualified violations, raised as `INVALID_ARGS` to the model, which
fixes its own call. Our `argus/gaming/mini_agent.py` ends an episode on a malformed call, which is right for an
instrument (it is an outcome); a working agent (the observer's phase 2) should do what they do.

## 3. A sanctioned "I can't" exit

`packages/goal/goal` + `goal/tool-goal`: a long-running objective that the model may mark complete OR blocked (with a
stable policy code and an explanation); automatic continuation is capped (256 rounds by default) and exhaustion records
a blocker. **This is the volunteered-abstention channel our pilot lacked**: v1 can give the agent a `block(reason)`
tool beside `finish`, so "this is impossible" is an action the instrument sees, not a questionnaire answer afterwards.

## 4. Oversized tool output: head and tail, not head only

`packages/compaction/compaction-tool-result-pruner`: over-budget output becomes a bounded head, a "middle pruned"
marker and a bounded tail; the full result stays in the session log. Our tool plumbing hard-truncates (100k chars in the
TSX bash tool); errors and summaries usually sit at the END of command output, so head+tail is the better cut.

## Not adopted / not relevant

Their UI, desktop app, provider accounts, cloud tools. Retries (`llm/llm-retry`) happen at agent-step boundaries with
malformed provider responses retryable; we already handle that per request.
