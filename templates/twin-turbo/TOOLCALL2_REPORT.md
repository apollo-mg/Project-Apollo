# `chat_template-toolcall2.jinja` — one release-blocking regression

**Tested 2026-09-12** at DavidAU's request, before re-GGUFing. Snapshot of the file as posted:
`data/receipts/svgbench-davidau/toolcall2_asof_2026-09-12.jinja`.

## Verdict: do not ship as posted

**It crashes on every tool call whose `arguments` is a JSON string** — which is the OpenAI format,
and what llama-server itself emits.

| `arguments` shape | `toolcall2` as posted | `tturbo` (current) | `toolcall2` + guard |
|---|---|---|---|
| **JSON string** `'{"path":"a.txt"}'` | **CRASH** | OK | OK |
| dict `{"path": "a.txt"}` | OK | OK | OK |

Error: `TypeError: Can only get item pairs from a mapping.` at template line 282.

## Cause: a guard was lost in the merge

`toolcall2.jinja:281-288` calls `|items` after checking only that `arguments` is defined and
non-empty:

```jinja
{%- if tool_call.arguments is defined and tool_call.arguments != '' %}
    {%- for args_name, args_value in tool_call.arguments|items %}
```

The `tturbo` template that this supersedes guards it properly (`:555-584`) with a three-way branch:
`is mapping` → emit `<parameter=…>` tags; `is string` → emit raw; otherwise `tojson`.

## Minimal fix

Wrap the existing loop and add the else branch:

```jinja
{%- if tool_call.arguments is defined and tool_call.arguments is not none and tool_call.arguments != '' %}
    {%- if tool_call.arguments is mapping %}
        {%- for args_name, args_value in tool_call.arguments|items %}
            {{- '<parameter=' + args_name + '>\n' }}
            {%- set args_value = args_value | string if args_value is string else args_value | tojson | safe %}
            {{- args_value }}
            {{- '\n</parameter>\n' }}
        {%- endfor %}
    {%- else %}
        {{- tool_call.arguments if tool_call.arguments is string else tool_call.arguments | tojson }}
    {%- endif %}
{%- endif %}
```

Patched file: [`toolcall2_arguments_guard.jinja`](toolcall2_arguments_guard.jinja).

## Everything else in it is correct

With that one guard added, the full battery passes:

- **17/17** crash-fuzz cases render, including every path that 500s on the unpatched original —
  `{REASON:high}`, a mode in CAPS, a missing brace, whitespace, an inner brace, a 500-char value,
  and a user quoting the tag syntax.
- **`tool_calls` are preserved in multi-turn history** — the original defect is fixed.
- **Tools are injected in both thinking modes**, with name, schema and `<tool_call>` instructions
  present whether thinking is on or off.
- **All five reasoning modes render and inject distinct text:** medium +0, low +138, xhigh +209,
  einstein +1,082, spoon +3,989 characters.
- donboyle's role guard and allow-list are both present and working.

So it is one line away from correct.

## Reproduce

```
tools/svgbench/reason_tag_crash_check.py <template.jinja>
```
