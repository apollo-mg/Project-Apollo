# Result — v5 bit-depth run cannot complete: the two protocol changes are arithmetically incompatible

**Date:** 2026-09-09. **Run:** `bitdepth_iq3xxs_v5`, GSQ-RCO Qwen3.8-27B IQ3_XXS, VBR, no MTP.
**Server:** pid 1982399, up 3h45m, never restarted.

## Finding

Every task from `t04_search_grep` onward — **13 consecutive, 3.5 hours** — died at the full
960 s timeout with `INFRA_ERROR`. Not one completed. The cause is not server degradation and
not the VBR clamp. It is arithmetic between two protocol changes I recorded in
`PREREG_BITDEPTH_AGENTIC.md` without checking their interaction.

## Mechanism (confirmed from source + live logs)

The model does not terminate: it generates to whatever output cap exists and returns
`finish_reason='length'`. The agent responds by **doubling the cap and re-issuing**:

`agent/turn_iteration_prep.py:382-391`
```python
_boost = (agent.max_tokens or 4096) * (2 ** length_continue_retries)
_boost_cap = max(32768, _requested_cap or 0)
agent._ephemeral_max_output_tokens = min(_boost, _boost_cap)
```

Observed in `traces/.../run_agent.log`:
```
🔄 Making API call #1/10...
⏱️  API call completed in 171.96s
⚠️  Response truncated (finish_reason='length') - model hit max output tokens
↻ Requesting continuation (1/4)...
🔄 Making API call #2/10...
```

With base 4096, measured per-call from the server log (n=15 and n=14 respectively):

| call | cap | prefill | decode | call total |
|---|---|---|---|---|
| #1 | 4096  | 16.6 s | 153.3 s | **169.9 s** |
| #2 | 8192  | 0.4 s (cache reuse) | 301.7 s | **302.1 s** |
| #3 | 16384 | — | killed mid-flight at 960 s | ~488 s served |

**A task whose continuation *also* runs to the boosted cap cannot finish inside the timeout**
(169.9 + 302.1 = 472 s, leaving 488 s of a call that needs ~618 s).

This is narrower than it first appears, and one task disproves the stronger version:
`t02_file_read/t03_read_paginated` hit `finish_reason='length'` **once**, took the continuation,
the continuation terminated naturally, and the task **completed in 284 s** (as FAIL, on content).
A single continuation is survivable. It is the *second* rung that is fatal.

## Corroboration

- Server log: **15 completed generations ended at exactly 4096**, **13 at exactly 8192**.
  Third calls (16384) never complete — no `eval time` line — because the harness kills the task first.
- Agent logs: `Requesting continuation (1/4)` ×14, `(2/4)` ×13. Ladder depth 2, never 3.
- **15 of 30** task logs hit `finish_reason='length'`.
- Affected tasks make exactly **3 API calls** of their `--max_turns 10` budget, then die.

## What this is NOT

- **Not the VBR floor clamp.** 14 clamp events, spread evenly across the whole run including
  the healthy first 13 minutes. Consistent with the prior finding that the clamp is benign.
- **Not MTP collapse.** `--spec-type` is absent from the server command line; MTP is not active.
- **Not server degradation.** At the time of diagnosis: decode **26.5 t/s**, prompt eval
  **769 t/s**, cache LCP similarity **0.997** with 13162/13203 tokens reused. The server is healthy.
- **Not the truncated-tool-call ladder** (`turn_truncation.py:278`). Same doubling arithmetic,
  but **zero occurrences** in 30 task logs. I proposed this first; the logs falsified it.

## Two reporting errors made and corrected today

1. Reported "14 PASS / 2 FAIL, infra 27%, run in progress" as healthy progress. The PASS/FAIL
   counts were **entirely pre-14:03**; the run had been dead for 3.5 h and the rising count was
   pure INFRA_ERROR accumulation. Reading a frozen tally as forward motion — same family as AFM-34.
2. Called the signature "the wedge we root-caused" on 16-minute-interval timeouts alone,
   before reading the server log. The interval was the timeout period itself, not a wedge.

## RESOLVED — `HERMES_MAX_TOKENS` is inert, and the ladder is NOT configurable

Measured, not inferred. A local stub was pointed at `run_agent.py` to capture the outgoing
request body (zero GPU cost):

| probe | env | outgoing `max_tokens` |
|---|---|---|
| A1 | `HERMES_MAX_TOKENS=1024` | **absent** — keys were `[messages, model, stream, stream_options, tools]` |
| A2 | unset, 9 calls | **absent on all 9** |

Source confirms why. `run_agent.py:1477`:
```python
agent = AIAgent(base_url=base_url, model=model, api_key=api_key, max_iterations=max_turns,
                enabled_toolsets=..., disabled_toolsets=..., save_trajectories=..., ...)
```
**`max_tokens` is never passed**, so `agent.max_tokens` keeps its default `None` (signature line 259).
`HERMES_MAX_TOKENS` is read only in `cli.py`, `gateway/run.py`, and `api_server.py` — **none of which
is the `run_agent.py` path** that hermesbench drives.

### The consequence that matters for v6

The ladder base is `(agent.max_tokens or 4096)` with `agent.max_tokens is None`, so it is
**hard-anchored to 4096** and is not reachable from any env var or server flag. The boosted value
is injected into the request by `_consume_ephemeral_max_output()`
(`agent/chat_completion_helpers.py:1381`), and **an explicit request `max_tokens` overrides the
server's `-n`.** Therefore:

- `-n` bounds **call #1 only**.
- Calls #2-#5 are **8192 / 16384 / 32768 / 32768 regardless of `-n`**.
- Worst case for a single runaway turn: 4096+8192+16384+32768 = **61,440 tokens ≈ 2,318 s** at 26.5 t/s.

**Lowering `-n` will not fix this run.** The only effective levers are the task timeout,
`--max_turns`, or patching the agent. The prereg's `HERMES_MAX_TOKENS=4096` was a no-op:
it neither caused nor could have prevented the failure.

*Caveat:* probes A1/A2 never entered the continuation path — the stub returns plain JSON while
the agent requests `stream: true`, so the rung values above are read from source plus the server's
own record of 14 generations ending at exactly 8192, not captured on the wire.

## RESOLVED — task type is NOT the cause; it is server-side state

**Probe B:** `t04_search_grep/t01_basic` re-run **first**, on a **freshly restarted server**,
settings otherwise identical to v5. **Result: PASS.** Two API calls, zero `finish_reason='length'`,
zero continuations. In v5 that same task ran 17th and was INFRA_ERROR with a full runaway.

| | v5 (17th) | probe B (1st) |
|---|---|---|
| call #1 prompt | ~4,647 tok | ~4,644 tok |
| call #1 | 171.8 s, `finish_reason=length` | **20.8 s, `stop`** |
| call #2 | 305.7 s, `length`, still **2 messages** | 3.3 s, **4 messages** |
| outcome | INFRA_ERROR | **PASS** |

Two things this settles:

1. **Not task-type.** Prompts differ by 3 tokens; behaviour is opposite.
2. **Not accumulated agent context.** The prompt is not bloated in either run (2 messages,
   ~4.6k tokens both). v5's shared `HERMES_HOME` had grown to 35 MB/5436 files, but almost all of
   that is a vendored pyright install, and none of it reaches the prompt.

**The failure is that the model stops emitting tool calls.** In v5, call #2 still has only
2 messages — no tool result ever came back, because no tool was ever called. It generates prose to
the cap, gets continued, and generates to the cap again. On a fresh server the same prompt produces
a tool call in 20.8 s.

### Leading hypothesis (NOT yet tested)

Cross-task prompt-cache reuse. From the v5 server log on a stuck task:
```
cache_plan_s: selected slot by LCP similarity, f_sim_best = 0.997, f_keep = 0.762
edit/divergence (cached/incoming/lcp/reusable/rewind/append/cache_prompt)
                = (17264/13203/13162/13162/4102/41/1)
restored context checkpoint (pos_min = 13047, n_tokens = 13048, size = 149.626 MiB)
CHECKPOINT_ATTN_ONLY_TRIM p0=13048 target=1 draft=0
```
The server restored a checkpoint holding the **previous task's** 17,264-token context, rewound
4,102 and appended 41, to serve a 13,203-token incoming prompt. The system prompt is byte-identical
across tasks (established earlier: SHA match, 35,207 chars), which is exactly what makes LCP
similarity high enough to select a foreign slot. If that rewind is not semantically clean, the
model is decoding against another task's tail — which would explain degenerate, non-terminating
output from a clean-looking prompt.

**This is a hypothesis with a mechanism, not a result.** It is consistent with `server-uptime-is-a-variable`
(AFM-26), except the degradation here is in stopping behaviour, not speed — decode was a healthy
26.5 t/s throughout.

**Discriminating test for v6:** re-run the v5 sequence with context checkpoints disabled
(or `--cache-reuse 0`). Runaways vanish → cache reuse. Runaways persist → plain uptime degradation.
A cheaper first cut: restart the server every N tasks and see whether onset tracks N.

