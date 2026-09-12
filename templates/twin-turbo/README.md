# Twin-Turbo chat template — the tool-calling fix

**What this is.** A one-line correction to the chat template shipped with
[DavidAU/Qwen3.8-27B-TWIN-TURBO-Fable-Cold-Fusion-709-L-Uncensored-NM-DAU-NEO-MTP-GGUF][model].
DavidAU has adopted it and published it on the model repo ([discussion #10][disc]).

File: [`twin_turbo_template_fixed.jinja`](twin_turbo_template_fixed.jinja).
To use it: save, rename to `chat_template.jinja`, and point `llama-server --chat-template-file` at
it (or whatever your harness uses).

[model]: https://huggingface.co/DavidAU/Qwen3.8-27B-TWIN-TURBO-Fable-Cold-Fusion-709-L-Uncensored-NM-DAU-NEO-MTP-GGUF
[disc]: https://huggingface.co/DavidAU/Qwen3.8-27B-TWIN-TURBO-Fable-Cold-Fusion-709-L-Uncensored-NM-DAU-NEO-MTP-GGUF/discussions/10

## The bug

The template adds an in-message `{REASON:mode}` parser. To strip that tag it rebuilds **every**
message as a fresh `{role, content}` pair:

```jinja
{% set store.messages = store.messages + [{"role": msg.role, "content": txt}] %}
```

An assistant turn that made a tool call carries its call in `msg.tool_calls`, not in `msg.content`.
Rebuilding the message keeps only `role` and `content`, so **the tool call is silently dropped from
the conversation history**. The assistant's turn renders empty where the stock Qwen3.8 template
renders `<tool_call>…</tool_call>`.

The model then sees a history in which it apparently said nothing, and multi-turn tool use falls
apart. This matches the user report on the model repo.

## The fix

Only messages that actually carry a `{REASON:…}` tag need rebuilding. Everything else passes
through whole:

```jinja
{% set store.messages = store.messages + [msg] %}
```

Tagged messages still get rebuilt, because their text genuinely has to change once the tag is
stripped. Untagged messages — including every assistant turn holding `tool_calls` — are preserved
intact.

## How it was verified

Two independent checks, not just a reading of the code:

1. **Rendered both templates** with jinja2 against a conversation containing a tool call, and
   diffed the output. The shipped template emits an empty assistant turn; the fixed one emits the
   `<tool_call>` block, matching stock Qwen3.8.
2. **Asked llama-server itself.** Loading the model with each template and reading `/props`:

   | template | `supports_tool_calls` | parallel tool calls |
   |---|---|---|
   | as shipped | `false` | `false` |
   | fixed | **`true`** | **`true`** |

   The server's own capability probe flips. That is the check that cannot be argued with, because
   it is the harness reporting what it can do, not us reporting what we think it should do.

Working notes, probe output and the rendering diff:
[`data/receipts/svgbench-davidau/NOTE_TEMPLATE_TOOL_CALLS.md`](../../data/receipts/svgbench-davidau/NOTE_TEMPLATE_TOOL_CALLS.md).

## Notes from DavidAU

- Reasoning should be on; instruct mode for tool calls is poor.
- Q6 or Q8 for best quality; Q4_K_M / Q5_K_M may be workable.
- Temperature 0.6–0.7.

## Provenance

Found and fixed 2026-09-11 while measuring this model's thinking-token claims on a separate
benchmark ([`svgbench-davidau/RESULT_TOKENS.md`](../../data/receipts/svgbench-davidau/RESULT_TOKENS.md)).
The template bug was incidental to that work and is unrelated to its result.

The copy DavidAU links is pinned to commit `ea693f9` at
`data/Apollo Docs/twin_turbo_template_fixed.jinja`; the file here is byte-identical and is the
maintained location.
