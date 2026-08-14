# The coordinator invalidates its prompt-cache prefix on every turn

**Date:** 2026-08-14 · **File:** `engines/open-multi-agent-upstream/examples/apollo_server.ts:449-479, 570`
**Status:** diagnosed, NOT yet fixed. No measurement taken — see Limits.

## Where this came from

Reading `deepseek-ai/deepseek-harness` (published 2026-08-13) after two independent
reports of "up to 100% cache hits". The mechanism is stated plainly in its
`docs/subsystems/system-prompt.md`:

> `PromptContext` is the **cache-safe** counterpart to `PromptSection`. The assembly
> resolves and orders these contributions, while agent-loop logs their complete current
> snapshot **after retained model history** only when it changed or compaction removed it.

Volatile content goes *after* the stable history, never into the system prompt. Their
session log is append-only and the message history is **derived** from it, so the prefix is
stable by construction rather than by discipline.

That claim is about the harness, not the model, and says nothing about answer quality —
it means the harness doesn't sabotage the cache. Which is exactly the part that ports.

## What Apollo does instead

`systemPromptStr` is assembled per request from four sources, three of them volatile:

| line | appended | volatility |
|---|---|---|
| 449-453 | `profile.system_instructions` or `SOVEREIGN_PROMPT` | stable per profile |
| 455-463 | `profile.memory_file` (`LOCAL_AGENT_CONTEXT.md`, **8785 B ≈ 2.2k tok**) | changes whenever the file is edited — and it is edited to steer live agent behaviour |
| 465-472 | `DRIFT_WARNING.md` (355 B) | appears/disappears with `run_diagnostics.sh` |
| 474-484 | `searchMemory(userText)` — **hybrid search keyed on the user's message** | **changes every single turn, by construction** |

Line 570 then prepends `<|think|>\n` to the whole thing.

The last one is decisive. `searchResults` is a function of `userText`, so the system prompt
differs on every turn of every session. A prompt cache matches on a **common prefix**; one
changed byte near the front invalidates everything after it. Retrieved skills are injected
at the front, so **the entire prompt re-prefills every turn** — including the ~2.2k tokens
of `LOCAL_AGENT_CONTEXT.md` that never changed.

## Why this matters more here than for a cloud harness

Apollo's binding constraint is prefill on Pascal. `data/receipts/mtp-sm60/SUMMARY.md`
measures P100 decode at 11.87 tok/s, and prefill is what the operator pays on every turn
before a single token is emitted. llama.cpp keeps a prompt cache; a stable prefix is what
lets it skip work it already did.

The irony worth recording: the sole reason this content is placed early is *importance* —
memory anchor first, drift warning next, retrieved skills last. Cache-wise that ordering is
exactly backwards. **Order by volatility, not by priority.**

## The fix, smallest form

Split the assembly at the volatility boundary:

- **Prefix (cached):** `SOVEREIGN_PROMPT` / `system_instructions` + `memory_file`. Stable
  for the life of a profile.
- **Tail (not cached):** `DRIFT_WARNING.md` + `searchMemory()` results, moved out of
  `systemPrompt` and into the first user-turn content, or a trailing context block after
  retained history — the `PromptContext` position.

This is a reordering, not a redesign. Nothing is dropped; the model sees the same bytes in
a different position.

One caveat that must be tested rather than assumed: instruction-following on heavily
quantised local models is sensitive to placement, and `data/receipts/` already documents
these models as "structurally brittle under multi-turn JSON tool schemas". Retrieved skills
arriving after history instead of in the system prompt may change behaviour. That is a
measurement, not a prediction.

## Limits — nothing here is measured yet

- **No cache-hit rate was recorded**, before or after. This is a code-reading finding.
- llama.cpp's prompt-cache behaviour under this server's request shape is **not verified**;
  whether it caches across turns here depends on the endpoint and flags in
  `scripts/startup/`, which were not inspected.
- The prefill cost of the ~2.2k-token memory file is **inferred from its size**, not timed.
- No claim is made about quality impact in either direction.

**To make this a result rather than a hypothesis:** time first-token latency over a
5-turn session before and after the reordering, on one profile, same model and flags,
both orderings run — and record whether tool-call validity changes, since that is the
failure mode this fleet actually suffers.
