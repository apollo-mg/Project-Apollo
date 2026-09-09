# RESULT: the agent-corpus runaways are a harness defect — declared token budgets are never applied

**Date:** 2026-09-09 · **Repo:** `~/projects/hermes-bench-tool-call`
**Question:** why do tasks generate 8,300–9,400 tokens and die on the wall clock?

## Answer: the corpus declares a token budget and the runner ignores it

Every task in the corpus specifies:

```yaml
max_tokens: 4096
timeout_seconds: 60
sampling: {temperature: 0.0, top_p: 1.0, top_k: -1, seed: 42}
```

`TaskSpec.from_yaml` parses all three (`types.py:106,110,136,140`). The runner then uses
**`allowed_tools, difficulty, hermes_plugins, id, isolated_network, latency_injection_ms, max_turns,
model_endpoint, prompt, resource_limits, timeout_seconds, verifier`** — and nothing else.

```
$ grep -rn 'task\.max_tokens\|task\.sampling' hermesbench/
(no output)
```

**`task.max_tokens` and `task.sampling` are parsed and never referenced.** The only `max_tokens` in
the package is `"max_tokens": 1` in preflight health probes.

### Consequences

1. **Generation is unbounded.** Tasks declaring 4096 produced 8,332 / 8,334 / 8,393 / 8,518 / 8,640
   (IQ2_M) and 9,178 / 9,379 / 8,850 (IQ3_XXS). Every one of those is ≈ wall-clock-timeout × decode
   rate — they were cut off by the client, never by a budget.
2. **The corpus was designed for determinism and has never had it.** `temperature: 0.0, seed: 42` is
   declared per task and never applied; hermesbench sends no sampling at all, so the *server's*
   defaults win. Every run in this campaign has been non-deterministic by accident.
3. **This resolves an open puzzle.** det02 (3-bit, MTP on) passed `t02_read_missing` and
   `t02_read_nested`; the `bitdepth_iq3xxs` arm (3-bit, MTP off) ran away on both. With the declared
   seed never applied, that is ordinary run-to-run variance — not evidence that speculative decoding
   changes output.

**The corpus authors anticipated runaways and set a 4096 budget to prevent them. The runner drops it.**

## Compounding: neither budget layer works

- **Task layer:** `max_tokens: 4096` parsed, never sent.
- **API layer:** even when sent, `max_tokens` does not bound generation on buun `3823c9eb6` — a
  request with `max_tokens: 400` reached **n_gen 14,039** and was still generating
  (`RESULT_TURBO_IQ2M_WALLED.md`).

Two independent places a token budget should have applied. Neither did. The 360 s wall-clock timeout
was the only backstop, and it converts verbosity into a scored INFRA_ERROR.

## A second, separate defect: `t05_read_nested` is unsatisfiable as written

```yaml
name: "Read a deeply-nested path"
prompt: Read `add.py` (note the path is in a subdirectory).
fixture: {source: small_repo, globs: ["**/*"]}
```

The materialised worktree contains **nine files, all in the root, no subdirectories anywhere**.
`add.py` is at the top level. The prompt asserts a path structure that does not exist.

Its verifier checks only that `read_file` was called **at all** — not which file, not what was
reported:

```python
used = any(tc.function.name == "read_file" for msg in trace if role=="assistant" ...)
return PASS if used else FAIL
```

So a model that **ignores** the misleading hint and reads `add.py` passes immediately, while a model
that takes the prompt seriously searches for a nonexistent subdirectory and never terminates.
**AFM-31 exactly: contradictory instructions reward the model that ignores them.**

Related: `t02_read_tail` asks for *"the last 20 lines"* of a **10-line** file. `t01_read_head` asks
for the first 50 of the same file and passes, so over-asking is not fatal on its own — but combined
with an unbounded budget it is another task with no clean stopping condition.

## Why the runaways clustered on `t02_file_read`

`t04_read_missing` ("Read `nonexistent.py`") is a **legitimate** false-premise test — deliberate, and
the model is asked to handle the error. `t05_read_nested` is an **accidental** one. Both require the
model to establish an absence, and per A5: *"concluding 'no such thing exists' means EXHAUSTING a
search; answering terminates on a hit."* With no token cap, exhausting a search has no end.

## What this retracts

`RESULT_TURBO_IQ2M_WALLED.md` attributed the bimodal generation pattern (~100 tokens or ~8,300) to
IQ2_M quantisation and scored P3 as confirmed. **Withdrawn.** The 3-bit arm shows the identical shape,
and the cause is an unenforced budget plus false-premise tasks — not bit depth. Whether the runaway
*rate* differs by quant remains open and is what `PREREG_BITDEPTH_AGENTIC.md` measures.

## For am423

Three concrete defects, in priority order:

1. **`task.max_tokens` is parsed and never applied.** Tasks cannot bound their own generation. This
   is the direct cause of wall-clock failures being scored as infrastructure errors.
2. **`task.sampling` is parsed and never applied.** The corpus specifies `temperature: 0.0, seed: 42`
   for reproducibility and does not get it.
3. **`t02_file_read/t05_read_nested` is unsatisfiable as written** — the prompt asserts a subdirectory
   the fixture never creates, and the verifier only checks that `read_file` was called once.
