# Qwen3.8's chat template: three defaults that compound, and buun's fixes did not survive the rewrite

**2026-08-16.** Source: `Qwen/Qwen3.8-27B` `tokenizer_config.json`, compared against
`buun_q36_chat_template.jinja` ("Qwen3.6 Barubary Chat Template v2", 25 numbered fixes over the
official 3.6 template, targeted at Qwen3.5-*/3.6-*).

## Three defaults, verified in the template source

```jinja
{%- set resolved_reasoning_effort = reasoning_effort|default('xhigh') %}
{%- if preserve_thinking is undefined or preserve_thinking is true or ... %}
```

| default | value | consequence |
|---|---|---|
| `reasoning_effort` | **`xhigh`** | injects *"think carefully... consider plausible alternatives"* — maximum exploration |
| `preserve_thinking` | **on** (undefined evaluates true) | every prior assistant turn's thinking is replayed into the prompt |
| `cache_prompt` (server-side) | **true** | prefix reuse, and reuse changes temp-0 output — see `INDEX.md` |

Individually defensible. Together, a long agentic loop runs at maximum reasoning effort while
carrying a growing tail of all previous reasoning, served from a reused prefix. buun's template
sets `preserve_thinking` **opt-in, default false**, explicitly "for stateless API servers".

Measured consequence of the first one: HLE parse rate **0 % at `xhigh`, 80 % at `low`**, same
model, same server, same sampling, 6.3x fewer tokens (`hle-mini/POWER.md`).

## The 3.6 -> 3.8 rewrite dropped fixes buun had already made

3.6's template has **no** `reasoning_effort`; 3.8's has it (`xhigh`/`medium`/`low`). In the same
release the card's *third* sampling set — "thinking mode for precise coding tasks,
`temperature=0.6`" — disappeared, leaving only thinking-general (1.0) and instruct (0.7). The
knob moved from sampling parameters into the chat template. **The widely-repeated "use temp 0.6
for coding on Qwen" advice is 3.6-era and obsolete on 3.8.**

But the rewrite did not incorporate buun's compatibility work:

| buun fix (3.6 v2) | present in official 3.8? |
|---|---|
| #7 remove `\| safe` filter (llama.cpp compat) | **still present** |
| #11 replace `loop.previtem` / `loop.nextitem` | **still present x3** |
| #17/#20 graceful fallback instead of `raise_exception` | **9 raise sites remain** |
| #3 `developer` role (Claude Code / Codex / OpenCode) | **still absent** |
| #23 `preserve_thinking` opt-in | present, but **defaults ON** (buun: off) |
| #25 fuzzy `</think>` parsing | some handling present |

The four unaddressed ones are exactly the minja-stability and agentic-robustness class. The
missing `developer` role matters for anyone driving these models from Claude Code or OpenCode,
which emit that role.

## What this does NOT explain

Our HLE truncations were checked for malformed `</think>` variants (buun's #25) across 20
traces: **none found**. The pattern is clean — `finish_reason=stop` always has content,
`finish_reason=length` always has content 0. The failures never reached a close tag because
generation was cut off mid-thinking, not because the tag was mis-parsed. Template parsing is
not implicated; `reasoning_effort` remains the explanation.

## Open

- Whether a 3.8-targeted version of buun's template (a "v3") changes any measured behaviour, or
  only robustness. Untested.
- `preserve_thinking=false` on long agent loops: unmeasured here, but it is the default that
  most directly interacts with the prefix-cache findings in `INDEX.md`.
