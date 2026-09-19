# Finding -- Bonsai 2 drops the `high` -> `xhigh` alias, making a documented value a hard error

**2026-09-19, found mid-panel.** Prompted by Mark asking whether Bonsai kept the reasoning modes
intact in its chat template -- a question that, had the answer gone the other way, would have
silently invalidated the agentic panel.

## First: the panel is NOT confounded

Chat templates extracted from the GGUFs and rendered with identical inputs:

| `reasoning_effort` | stock Qwen3.8-27B | Bonsai 2 PQ2_0 | identical |
|---|---|---|---|
| **medium** (what the panel uses) | 60 chars, sha `cf3fd97abdad` | 60 chars, sha `cf3fd97abdad` | **YES, byte-identical** |
| xhigh | 297 chars, sha `0a7393b3d4d0` | 297 chars, sha `0a7393b3d4d0` | yes |
| low | 226 chars | 226 chars | yes |
| **high** | 297 chars (silently aliased to xhigh) | **raises an exception** | **NO** |

Every arm in the panel sees a byte-identical prompt. The comparison stands.

## The defect

Bonsai 2's template is **1,041 characters shorter** than stock and is missing this block:

```jinja
{%- if resolved_reasoning_effort == 'high' %}
    {%- set resolved_reasoning_effort = 'xhigh' %}
{%- endif %}
```

Without it, `high` falls through to the validation guard that follows:

```
Unexpected reasoning effort high. Supported types are xhigh (default), medium, and low.
```

**So `reasoning_effort: high` is a hard error on Bonsai 2 and a silent upgrade to `xhigh` on
stock.** `high` is a documented Qwen3.8 value and the most natural thing for a user to reach for.

**This is a packaging defect, not a weights defect.** It is the class of problem that makes a model
look broken while the tensors are fine -- and it is one line to fix.

## Incidentally confirms the effort cost, on both templates

`xhigh` injects **237 characters** that `medium` does not, and both templates agree on that figure.
This corroborates [[qwen38-effort-is-a-prompt-edit]] -- on Qwen3.8 `reasoning_effort` is a **prompt
edit**, not a sampling knob -- and it means public runs made at `xhigh` (Fateev's, per his posted
settings) were paying that cost on every turn but were **not** hitting this bug.

## Bonsai v1, for contrast

v1's template contains **no `reasoning_effort` handling at all** (0 occurrences, vs 6 in v2 and 8 in
stock). It predates the feature. So the reasoning plumbing is something v2 inherited and then
partially dropped, rather than something it never had -- consistent with the wider v1-to-v2 picture
in [[ANALYSIS_BONSAI_V1_VS_V2]]: the method changed, and pieces went missing in the port.

## Reproduce

```python
# extract tokenizer.chat_template from each GGUF, then:
env.from_string(tpl).render(messages=[{"role":"user","content":"hi"}],
                            add_generation_prompt=True, reasoning_effort="high")
# stock: renders, 297 chars.  Bonsai 2: RuntimeError, "Unexpected reasoning effort high".
```
