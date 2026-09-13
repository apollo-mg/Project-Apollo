# Result — the two engines disagree, and the Frogger template's reasoning modes are broken in both

**Run 2026-09-13, ~10:30–11:00.** Pre-registered in `PREREG_TEMPLATE_MINJA_DIFF.md` (`da70afd`), driver
`template_minja_diff.py`, raw rows in `results.jsonl`. Renders the same six conversations through
**llama.cpp's minja** (`llama-server --chat-template-file`, POST `/apply-template`, buun `da458765d`) and
through **Python jinja2 3.1.6**, comparing byte for byte.

**Good news first: our patch shipped.** DavidAU's `chat_template.jinja` is now byte-identical to
`chat_template-toolcall2.jinja`, and the guard we supplied is at line 284.

## Findings

### 1. The default template crashes in transformers on OpenAI-standard tool calls

| case | minja | Python jinja2 |
|---|---|---|
| plain, tools, `{REASON:einstein}` | **identical** | **identical** |
| tool round trip, `arguments` as a JSON string | renders correctly | **TypeError: "Can only get item pairs from a mapping"** |

**Line 282** is the site:

```jinja
{%- for args_name, args_value in tool_call.arguments|items %}
```

It iterates `arguments` **as a mapping**, but the OpenAI wire format sends it as a **JSON string**.
**minja's `items` parses that string; Python jinja2's does not**, so it raises. minja's output is correct
— `<parameter=city>\nChengdu\n</parameter>` — so llama.cpp users see nothing wrong.

**The guard we supplied protects the wrong level.** Line 284 coerces each *value*
(`args_value | string if args_value is string`), which never fires when the whole `arguments` field is a
string. **The same template ships in the safetensors repo**, so anyone loading it with transformers
crashes on any conversation containing tool-call history.

**Shape of a fix** — branch at the container, not the value:

```jinja
{%- if tool_call.arguments is string %}
    {{- tool_call.arguments }}
{%- else %}
    {%- for args_name, args_value in tool_call.arguments|items %} … {%- endfor %}
{%- endif %}
```

### 2. The Frogger template uses an undefined variable, and both engines fail differently

`chat_template-tturbo.jinja` (`template_version = "qwen3.8-froggeric-v22.5.0-DAU-Twin-Turbo-V1.0"`) at
**line 228**:

```jinja
{% set candidate = txt.split("{REASON:")[1].split("}")[0] if (…) else "" %}
{% if candidate and candidate_key in ('xhigh', 'medium', 'low', 'einstein', 'spoon') %}
```

**`candidate_key` is never assigned.** His own default template defines it one line earlier:

```jinja
{% set candidate_key = candidate[1:] if candidate.startswith('i') else candidate %}
```

**Measured consequences of that one missing line:**

| engine | what happens with `{REASON:einstein}` |
|---|---|
| **llama.cpp / minja** | **HTTP 500.** *"While executing BinaryExpression at line 228, column 37"* — the request fails |
| **transformers / jinja2** | **Silently ignored.** The persona is not injected, and the literal `{REASON:einstein}` is left in the prompt as user text |

Verified directly: with tturbo, `"Brainstormer" in prompt` is **False** and `"{REASON:einstein}" in prompt`
is **True**; with his default template the persona is injected and the tag is stripped. **So einstein and
spoon modes do not work at all through this template** — the flagship feature of the file — and a user
gets either an error or a silent no-op depending on their runtime.

### 3. The Frogger template also renders tool history differently per engine

Case 5 diverges at line 54: **minja** emits structured `<parameter=city>`, **jinja2** emits the raw
`{"city": "Chengdu"}`. Not a crash, but the same conversation becomes a different prompt depending on who
serves it.

## Predictions

| id | prediction | result |
|---|---|---|
| P-T1 | the default renders identically in all six cases | **FALSIFIED.** Identical for plain, tools and REASON; jinja2 crashes on string `arguments` |
| P-T2 | tturbo renders identically in all six cases | **FALSIFIED.** Case 5 differs, case 6 errors in minja |
| P-T3 | neither engine errors on the JSON-string arguments | **FALSIFIED.** jinja2 does, in both templates' path at line 282 / equivalent |
| P-T4 | `{REASON:einstein}` injects the persona under both engines | **CONFIRMED for the default, FALSIFIED for tturbo** |

## Is the Frogger template a good general Qwen 3.8 template?

**Not as it stands**, on this evidence:
- **The reasoning-mode path is broken** (finding 2), which is most of what distinguishes it.
- **It is opinionated by default.** A `terse` system instruction is injected unless the caller passes
  `{"terse": false}` — so anyone serving or benchmarking with it is also serving that prompt.
- **The einstein/spoon blocks embed `[Temperature: 1.25]` and `[TopP: .2]`** as text, which our own
  einstein receipt showed are inert strings, not sampler settings.

**What is genuinely good in it, and worth stealing:** it detects when a runtime has already injected its
own tool protocol (LM Studio's MLX backend prepends `[TOOL_REQUEST]`) and stands down rather than
emitting a second, contradictory protocol, with a `suppress_tool_instructions` kwarg to force the issue.
That is a real interoperability problem solved thoughtfully.

## Deviations

- **Cases 3 and 4 were malformed by me.** They end on an assistant message containing tool calls and ask
  for a generation prompt, which the server correctly refuses: *"Cannot continue an assistant message
  that contains tool calls."* Case 5 exercises the same rendering path validly, and is what the findings
  rest on.
- **The first run of this harness was invalid.** Its jinja2 environment used `trim_blocks=False,
  lstrip_blocks=False` where transformers uses both **True**, so every case reported a whitespace-only
  difference. Fixed before any finding was recorded; the corrected run is what appears above.
- **One model, one llama.cpp build.** minja behaviour is llama.cpp's, and says nothing about other
  runtimes' Jinja engines.
