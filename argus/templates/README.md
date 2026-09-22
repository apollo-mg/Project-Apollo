# Chat templates that work around llama.cpp parser defects

## `mimo_v26_distill_qwen9b_autoparser.jinja`

For `MiMo-V2.6-Distill-Qwen-9B`. **Renders byte-identically to the model's own embedded
template** (verified: same sha256 over a rendered prompt carrying two tool calls, two tool
responses, a system turn and a trailing user turn). Exactly one line differs.

Upstream:

```jinja
{{- '<parameter=' ~ args_name ~ '>' ~ render_value(args_value) ~ '</parameter>' -}}
```

Here:

```jinja
{{- '<param' ~ 'eter=' ~ args_name ~ '>' ~ render_value(args_value) ~ '</parameter>' -}}
```

### Why this works

`common/chat.cpp:1213` selects the specialized Qwen3-Coder parser by a **substring test over the
template source**: it fires when all three of `<tool_call>`, `<function=` and `<parameter=` appear.
That parser hardcodes the newline dialect and terminates a string argument only on the exact
sequence `"\n</parameter>\n"` (`common/parsers/qwen3-coder.cpp:92`). MiMo renders the **compact**
dialect, so the terminator never appears where expected and one argument consumes the tool calls
that follow it.

Splitting the literal means the source no longer contains `<parameter=`, the fingerprint misses,
and the template falls through to the **generic auto-parser**, which derives the format by running
the template and then explicitly relaxes whitespace on ending markers
(`common/chat-diff-analyzer.cpp:884`: *"always relax whitespace requirements on ending markers
since they don't influence content"*).

Measured on `bartowski/MiMo-V2.6-Distill-Qwen-9B-GGUF` Q8_0, RX 9070 XT, llama.cpp build 11095
(`58367713a`), vendor sampling (temp 0.6 / top_k 20 / top_p 0.95, `min_p` pinned 0.0):

| template | single call | two calls | two calls, `parallel_tool_calls=false` |
|---|---:|---:|---:|
| embedded (specialized parser) | 0/10 | **6/10 corrupt** | **6/10 corrupt** |
| this file (auto-parser) | 0/10 | **0/10** | **0/10** |

Confirmed on 30 further seeds (5000-5029), both arms, identical seeds:
**17/30 corrupt stock vs 0/30 fixed**, Fisher exact p = 6.2e-07.

Use with `--chat-template-file argus/templates/mimo_v26_distill_qwen9b_autoparser.jinja`.

### Caveats

- **This is a workaround, not a fix.** It exploits the selector being a substring test. If upstream
  tightens that fingerprint or changes the auto-parser, re-measure before trusting it.
- The auto-parser is a different code path with its own behaviour. It is verified here only for
  single-turn parallel tool calls on this model. **Multi-turn is unmeasured.**
- Re-run the check after any llama.cpp bump: `argus/templates/check_dialect.py`.
