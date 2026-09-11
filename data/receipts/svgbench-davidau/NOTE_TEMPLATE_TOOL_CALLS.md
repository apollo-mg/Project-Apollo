# Note — DavidAU's Twin-Turbo template drops the model's own tool calls from the conversation history

**Date:** 2026-09-11.
- **Checked with:** `render_toolcall_check.py`, using jinja2, with the templates read from the GGUF
  metadata.
- **Template:** from `…TTURBO-…-NEO-MTP-IQ3_M.gguf` (repo commit `7ee443a7`), 16,850 characters.
- **Prompted by:** Hugging Face discussion #7 on the model, "Agentic/tool-calling use: mid-tool-call
  stream drops + premature turn ends (base Qwen3.8 is fine in the same stack)".

## Finding

The template's `{REASON:…}` parser runs over every message and rebuilds it:

```
{% set store.messages = store.messages + [{"role": msg.role, "content": txt}] %}
…
{% set messages = store.messages %}
```

Everything except `role` and `content` is thrown away before the rest of the template renders,
including `tool_calls` on assistant messages. Rendering a one-call conversation (the user asks, the
assistant calls `get_weather`, the tool returns, the user follows up):

| template | the assistant turn that made the call |
|---|---|
| stock Qwen3.8-27B | `<tool_call><function=get_weather><parameter=city>Paris…</tool_call>` |
| Twin-Turbo as shipped | **empty:** `<think>\n\n</think>\n\n` |
| Twin-Turbo with the one-line fix below | identical to stock |

The tool result is still rendered, so the model sees a result it never asked for.

## Why it matters

**It fits the thread's symptoms.**
- llama.cpp's capability probe reports `supports_tool_calls: false`.
- Turns announce an action and end without calling anything. The model never sees an example of its
  own calls in the history.
- A replacement template reached the answer, though that was one run per template.

**It is a template bug, separate from the weights.** It does not show whether the shorter thinking
also costs agentic performance; answering that needs an agent test with the template fixed.

## The fix

Keep untagged messages whole in the parser's `else` branch:

```
{% set store.messages = store.messages + [msg] %}
```

- **Limit:** messages that carry a `{REASON:…}` tag are still rebuilt (to strip the tag), so a tagged
  assistant message would still lose its tool calls. Tags normally appear in user messages.
- **Patched copy:** saved as `twin_turbo_template_fixed.jinja`. Use it with `--chat-template-file`.

## Verification and limits

- **llama-server's own probe agrees.** This is `/props` → `chat_template_caps`, on buun `3823c9eb6`:

  | template | `supports_tool_calls` | `supports_parallel_tool_calls` |
  |---|---|---|
  | as shipped (16,850 chars) | false | false |
  | with the one-line fix (16,819 chars) | **true** | **true** |

  The raw output is in `props_embedded.json` and `props_fixed.json`, with server logs in `probe_*.log`.
- **Agent testing:** none yet with the fixed template. Whether the shorter thinking costs agentic
  performance on its own is untested.
