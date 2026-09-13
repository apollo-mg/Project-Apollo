# Prereg — does llama.cpp's minja render DavidAU's templates the same as Python jinja2?

**Written 2026-09-13 ~10:30, before any rendering.** This closes the item our own thread flagged as
untested: *"whether llama.cpp's minja parser behaves the same as Python jinja2 here — the authoritative
check is loading it in llama-server."*

## Why now

DavidAU has re-uploaded his Qwen3.8-27B GGUFs with the corrected tool template, and the default
(`chat_template.jinja`) is now **byte-identical to `chat_template-toolcall2.jinja`** — the file we
patched. Our fix is present at line 284:
`args_value | string if args_value is string else args_value | tojson | safe`.

He is also shipping `chat_template-tturbo.jinja` (638 lines), whose header reads
`template_version = "qwen3.8-froggeric-v22.5.0-DAU-Twin-Turbo-V1.0"` — **froggeric's community template
with his Twin-Turbo layer on top**. Mark asked whether that one is a good general Qwen 3.8 template.

**A template that renders differently under the two engines is a silent correctness bug**: it is authored
and tested against Python jinja2 (transformers), and served through minja (llama.cpp).

## Setup

- **minja:** `llama-server` from buun `da458765d`, ROCm build, with `--chat-template-file <template>`,
  rendering through **POST `/apply-template`**. The model is `Qwen3-0.6B-exl3` (a 3 s load); only the
  template matters, not the weights.
- **jinja2:** Python 3 with jinja2 3.1.6, rendering the same template text with the variables llama.cpp
  supplies (`messages`, `tools`, `add_generation_prompt`, `bos_token`, `eos_token`, plus any
  `chat_template_kwargs`).
- **Templates:** `chat_template.jinja` (= toolcall2, the new default) and `chat_template-tturbo.jinja`.

**Cases**, each rendered by both engines:
1. plain system + user
2. user only, with `tools` supplied
3. assistant `tool_calls` with **`arguments` as a JSON string** — the crash we reported
4. assistant `tool_calls` with `arguments` as an object
5. a full tool round trip: user → assistant tool_call → tool result → assistant
6. user message containing `{REASON:einstein}`

## Predictions

| id | prediction |
|---|---|
| P-T1 | The default template renders **identically** under both engines in all six cases |
| P-T2 | The tturbo template renders **identically** under both engines in all six cases |
| P-T3 | Neither engine errors on case 3, the JSON-string arguments that used to crash |
| P-T4 | Case 6 injects the einstein system text under **both** engines — the `{REASON:}` mechanism survives minja |

**Any difference is reported verbatim**, with the first differing line, rather than summarised.

## Declared in advance

- **Whitespace is compared exactly.** A trailing-space difference is a difference; it is reported as such
  rather than normalised away, because the prompt is what the model sees.
- **This tests rendering, not behaviour.** Identical prompts do not mean the template is a good idea; the
  `terse` injection (default on) and the einstein persona are style choices, and our own receipts show
  injected system text changes outputs.
- **One model, one build.** minja is llama.cpp's engine, so this is a statement about llama.cpp, not
  about other runtimes.

**Driver:** `template_minja_diff.py`. Results in this directory.
