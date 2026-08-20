# `reasoning_effort` is not a knob — it rewrites the system prompt

**2026-08-20.** Qwen3.8-27B-Q6_K chat template, pulled from the live server's `/props` on
`.194` and rendered with jinja2. Template source `/tmp/chat_template.jinja` (9,993 chars),
render verified against all five accepted values plus one rejected.

Prompted by Mark's read of bartowski's Qwen3.8 card. It checks out, and it is worse than a
formatting difference.

## What the template actually does

`reasoning_effort` is consumed by the **chat template**, which prepends a literal
`reasoning_instructions` string to the system message:

```jinja
{{- '<|im_start|>system\n' + (reasoning_instructions + '\n\n' if reasoning_instructions else '')
   + merged_system + '<|im_end|>\n' }}
```

Rendered system block, same messages, only the kwarg varying:

| `reasoning_effort` | system block | injected |
|---|---|---|
| **unset** | 237 chars | *"…set to **xhigh**. Please think carefully through the task, **validate key assumptions**, consider plausible alternatives, and prioritize correctness…"* |
| `xhigh` | 237 chars | identical to unset |
| `high` | 237 chars | **identical to unset** — silently remapped |
| **`medium`** | **0 chars** | **NOTHING** |
| `low` | 166 chars | *"…set to low. Keep your thinking brief and focused, **moving directly to the conclusion** without unnecessary elaboration."* |
| anything else | — | `raise_exception` |

## Three things that follow

### 1. "Default" is `xhigh`

`reasoning_effort|default('xhigh')`. Every run in this project labelled **`effort=default`
was running at `xhigh`** with a 237-character injected instruction. That includes both
`tier_cal` dry runs. The header line was not wrong about the setting; it was wrong that
"default" meant "nothing added".

### 2. There are only two branches, so `medium` is not a midpoint

The template has `if xhigh` / `elif low` and **no `medium` branch**. `medium` passes the
validator and then falls through, leaving `reasoning_instructions` empty. **`medium` is the
only setting that leaves the system prompt untouched.**

That is a mechanism for `BACKLOG C1` — Mark's *"medium is the sweet spot"* hypothesis. If
medium wins, the candidate explanation is no longer "an intermediate amount of thinking"; it
is **"the only setting that does not editorialise the prompt."** Those make different
predictions and C1 can now distinguish them.

### 3. `high` is a lie, including in our own tooling

`high` is silently rewritten to `xhigh`. `run_fixture.py --effort high` therefore offers a
choice that cannot do anything, and any receipt distinguishing `high` from `xhigh` is
comparing a value against itself.

## Why this matters for the calibration tier specifically

The `xhigh` string contains **"validate key assumptions"**. That is not a generic
thinking-harder instruction — it is close to a direct instruction to check premises, which is
exactly the operation a false-premise item tests. `low` says the opposite: *"moving directly
to the conclusion."*

So both `tier_cal` dry runs measured calibration **with a system-level instruction to validate
assumptions**, and the confabulation figure is conditional on that. `A1`'s open question
about effort is no longer speculative — it is a named string in the template, and the
plausible effect size is large enough that **effort may move calibration more than
quantisation does.** Until that is measured, effort must be **pinned and reported** with every
calibration number, exactly like clock and power state.

## The general rule

A parameter that arrives through the same API field as `temperature` and `top_k` looks like a
sampling knob. `chat_template_kwargs` is not a sampling knob — it is **prompt input**. There
is no way to tell which is which from the request body; the only authority is the template.

**Recorded as `AFM-23`.**

## Verification

```
GET /props -> chat_template (9993 chars)
jinja2 render, messages=[{role:user, content:"PROBE"}], add_generation_prompt=True
unset/xhigh/high -> 237 char system block, byte-identical
medium           -> 0 char system block
low              -> 166 char system block
"turbo"          -> RuntimeError('Unexpected reasoning effort turbo. Supported types are
                    xhigh (default), medium, and low.')
```

Note `/apply-template` does not exist on this build; the render is client-side against the
template the server reports, not the server's own rendering path. The two agreeing is assumed,
not verified — a residual gap worth closing if a number ever turns on it.
