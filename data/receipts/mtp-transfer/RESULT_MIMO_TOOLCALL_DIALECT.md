# MiMo-V2.6-Distill-Qwen-9B: llama.cpp cannot parse the tool calls its own template renders

**2026-09-22. RX 9070 XT (gfx1201), upstream llama.cpp build 11095 (58367713a), ROCm build_rocm.**
Model: `bartowski/MiMo-V2.6-Distill-Qwen-9B-GGUF` Q8_0.

**Prior art checked:** `ledger_precheck.py "llama.cpp tool call parser parallel multiple tool_calls XML
function parameter" --deep` -> found `svgbench-davidau/NOTE_TEMPLATE_TOOL_CALLS.md` and
`davidau-templates/RESULT_TEMPLATE_MINJA_DIFF.md`, both about rendering **history**, neither this.

**The precheck was not enough, and that is the first finding.** It indexes our receipts only. A
GitHub search found **ggml-org/llama.cpp#26763** (2026-08-08, MichaKPo), which reports this exact
mechanism, quotes the same three lines of `qwen3-coder.cpp`, and was **closed "Not a bug" on
08-09**. Searching upstream's issue tracker is not part of our precheck ritual and should be.
See "Relation to #26763" below for what this adds. **We did not discover this mechanism.**

## Headline

`common/chat.cpp:1213` routes any template containing `<tool_call>`, `<function=` and `<parameter=`
to the Qwen3-Coder parser. That parser hard-codes a **newline-delimited** dialect.
**MiMo's template renders the compact dialect. Zero of the five required literals appear.**

Round-trip, rendering an assistant turn with two tool calls through the model's own template
(`/apply-template`, so this is minja, the same renderer llama.cpp serves with):

```
'<tool_call><function=gmail_search><parameter=query>budget report</parameter></function></tool_call>
 <tool_call><function=calendar_list><parameter=start>2026-09-23</parameter>
 <parameter=end>2026-09-24</parameter></function></tool_call><|im_end|>'
```

| literal required by `common/parsers/qwen3-coder.cpp` | present in what the template renders |
|---|---|
| `'<tool_call>\n'` | **False** |
| `'<function=gmail_search>\n'` | **False** |
| `'<parameter=query>\n'` | **False** |
| `'\n</parameter>\n'` | **False** |
| `'</function>\n'` | **False** |

## Measured consequence

Vendor sampling (temp 0.6 / top_k 20 / top_p 0.95, `min_p` pinned to 0.0 -- see caveat below),
`enable_thinking=false`, 10 seeds per cell, two tools offered.

| prompt | corrupt | clean with calls | calls parsed per turn |
|---|---:|---:|---|
| needs ONE tool call | **0 / 10** | 10 | all 1 |
| needs TWO tool calls | **6 / 10** | 4 | mostly 2 |
| needs TWO, `parallel_tool_calls=false` | **6 / 10** | 4 | all 1 |

"Corrupt" means the parsed `arguments` JSON contains `</parameter>` or `<function=`, i.e. the
argument value swallowed the markup. A real example, verbatim from the API response:

```json
{"query":"budget report\n</parameter></function></tool_call><tool_call>\n
          <function=calendar_list>\n<parameter=start>\n2026-09-23"}
```

The first tool receives a garbage argument **and the second tool call disappears** -- it is inside
the first one's string. The HTTP status is 200 and `finish_reason` is `tool_calls`. Nothing in the
response says anything went wrong.

`parallel_tool_calls=false` is **not** a workaround. It changes the reported count to 1 but the
corruption rate is identical, because the model still generates both calls and the parser still
folds the second into the first one's argument string.

## Mechanism

`common/parsers/qwen3-coder.cpp:92`:

```cpp
auto arg_close  = p.tool_arg_close(p.literal("\n</parameter>\n"));
auto arg_string = p.rule("xml-arg-string",
    p.ac(p.tool_arg_string_value(p.until("\n</parameter>\n")) + arg_close, "\n</parameter>\n"));
```

A string argument ends **only** at the exact sequence `\n</parameter>\n`. MiMo emits
`</parameter></function>` with no surrounding newlines, so that sequence never appears at the
right place. `until()` compiles to a permissive GBNF rule ("any run of characters not containing
X"), so the grammar does not stop the model either -- it happily accepts the entire second tool
call as the first call's `query` string, then terminates at the *next* `\n</parameter>\n` it finds,
which belongs to a different call.

Single calls survive because the run-on hits EOS instead of a later parameter close.

## The mis-detection is specific to MiMo, not to the family

Fetched the official templates and grepped for the rendered literals:

| template | renders |
|---|---|
| `Qwen/Qwen3.5-9B` (MiMo's **base model**) | `<tool_call>\n<function=` and `\n</parameter>\n` -- newline form, **parser is correct** |
| `Qwen/Qwen3-Coder-30B-A3B-Instruct` | `\n</parameter>\n` -- newline form, **parser is correct** |
| `XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B` | compact, **parser is wrong** |

So llama.cpp's parser matches the models it was written for. **MiMo's SFT shipped a template that
diverges from its own base model's on whitespace only**, and that whitespace is load-bearing.
The `<tool_call>`/`<function=`/`<parameter=` triple in `chat.cpp:1213` is not a tight enough
fingerprint to notice.

## Control: swapping in the base model's template does not fix it

Relaunched with `--chat-template-file` set to Qwen3.5-9B's official template, same 30 requests:

| prompt | corrupt (MiMo template) | corrupt (Qwen3.5 template) |
|---|---:|---:|
| needs ONE tool call | 0 / 10 | 0 / 10 |
| needs TWO tool calls | 6 / 10 | **3 / 10** |
| needs TWO, `parallel_tool_calls=false` | 6 / 10 | **3 / 10** |

Halved, not fixed. This is the control that locates the defect: the dialect the model **emits** is
learned from SFT, so re-rendering the *history* in newline form only nudges it. The template swap
is a few-shot effect, not a fix. A real fix has to make the parser accept optional whitespace
around `<tool_call>`, `<function=...>`, `<parameter=...>` and `</parameter>`.

## Smoke test (the thing this started as) -- MiMo Q8 is otherwise healthy

| probe | result |
|---|---|
| load, `-ngl 99 -c 8192 -fa on -ctk f16 -ctv f16 -np 1 --jinja` | clean, 10.89 GiB of 15.92 GiB VRAM incl. compositor |
| plain generation, thinking off | 200, `content_len` 158, 30 tokens, 0.7 s |
| plain generation, thinking on | 200, `content_len` 215, 42 tokens, 0.8 s |
| termination ("count to 5 then stop") | `finish_reason=stop`, 10 tokens |
| single tool call | correct name and arguments, 10/10 |
| date arithmetic in a tool call ("tomorrow", told today is 2026-09-22) | `{"start":"2026-09-23","end":"2026-09-23"}` correct |

No empty-content-behind-200 was observed at `max_tokens` 1024-2048
(`[[thinking-off-in-harnesses]]` trap did not fire here, but `content_len` was checked separately
from status throughout, which is why we can say so).

## File identity

| file | bytes | source of truth |
|---|---:|---|
| `MiMo-V2.6-Distill-Qwen-9B-Q8_0.gguf` (local) | 9,545,979,424 | exact match to the HF API blob size for `bartowski/MiMo-V2.6-Distill-Qwen-9B-GGUF` |
| sha256 | `2fad0aa11bb9e7aa491ff12f768954f9dd0a6e7d4ce4a897ca73ec420f3b90ae` | recorded at fetch |
| `Ornith-1.5-9B-Q8_0.gguf` (bartowski) | 9,545,982,848 | exact match to the HF API blob size for `bartowski/Ornith-1.5-9B-GGUF` |
| sha256 | `c1f288e4975113e528070bacff1527cd895c3ff3f88b8e7f700fc788b537ce8d` | recorded at fetch |

`qwen35.block_count 32`, 427 tensors, blocks 0..31, `general.file_type 7`, context 262144.
Count and content agree -- this is the **correct** build, in contrast to `ggml-org`'s Q5_K_S which
declares 33 and ships 32 (`RESULT_MIMO_Q5KS_BROKEN.md`).

The local file arrived as `MiMo-V2.6-Distill-Qwen-9B-Q8_0 (1).gguf`. The " (1)" is a browser
rename, not a second copy: the byte count is exact. Symlinked to a space-free path at
`/mnt/TG_2TB/AI/Models/9b-panel/` before any script touched it.

## Side finding: the 9B panel's two Q8_0 files were from different packagers

The panel partner on disk, `Ornith-1.5-9B-Q8_0.gguf`, is **not** bartowski's.

| | bytes |
|---|---:|
| local `Ornith-1.5-9B-Q8_0.gguf` | 9,786,060,384 |
| `bartowski/Ornith-1.5-9B-GGUF` Q8_0 (HF API) | 9,545,982,848 |
| delta | 240,077,536 |
| local's `blk.32.nextn.*` MTP head, summed from `GGUFReader` | **258,557,952** |
| residual after removing the MTP head | **-18,480,416** |

The delta is *smaller* than the MTP head, so the difference is not only the head: the local build's
scored tensors are ~18.5 MB **smaller** than bartowski's. Two files, same label `Q8_0`, same
architecture, different recipe -- another instance of `[[gguf-label-is-not-a-spec]]`, caught by
summing tensor bytes rather than trusting the file delta (which is circular: it is the quantity
being explained).

`blk.32` is unambiguously the MTP head -- it carries `nextn.eh_proj`, `nextn.enorm`, `nextn.hnorm`,
`nextn.shared_head_norm`. This also explains the `ggml-org` MiMo break: Qwen3.5-9B derivatives have
32 real blocks plus an optional MTP head as block 32. `ggml-org` kept the count (33) and dropped the
head; the Ornith packager kept both (33/33, loads fine); bartowski dropped both (32/32).

Mark pulled bartowski's Ornith Q8 the same afternoon; it is verified at 9,545,982,848 bytes,
an exact match to the HF API blob size. The panel is now packager-matched -- and the two files
turn out to differ in the one way that matters here. See the control section above.

## The control that matters: the panel partner, same everything, 0/30

`bartowski/Ornith-1.5-9B-GGUF` Q8_0 is the intended comparison arm for the 9B panel. Same
packager, same architecture, same quant label, and structurally a near-twin:

| | MiMo-V2.6-Distill-Qwen-9B Q8_0 | Ornith-1.5-9B Q8_0 |
|---|---:|---:|
| bytes | 9,545,979,424 | 9,545,982,848 |
| tensors | 427 | 427 |
| blocks | 32 (0..31) | 32 (0..31) |
| `nextn` / MTP head | none | none |
| arch / file_type | qwen35 / 7 | qwen35 / 7 |
| context_length | 262144 | 262144 |
| **tool-call dialect rendered** | **compact** | **newline (`<tool_call>\n<function=`, `\n</parameter>\n`)** |

**3,424 bytes apart.** Same 9070 XT, same llama.cpp build 11095, same vendor-style sampling, same
prompts, same two tools, 10 seeds per cell:

| prompt | MiMo corrupt | Ornith corrupt |
|---|---:|---:|
| needs ONE tool call | 0 / 10 | **0 / 10** |
| needs TWO tool calls | 6 / 10 | **0 / 10** |
| needs TWO, `parallel_tool_calls=false` | 6 / 10 | **0 / 10** |

Ornith is clean on all 30 and returns 2 calls per turn where 2 are wanted. The entire difference
is whitespace in a Jinja template.

### Why this is the finding and not a footnote

The 9B panel exists to ask **"does agentic SFT beat a general fine-tune at equal parameters and
precision?"** Run as staged, it would have answered: *the agentic model is dramatically worse at
parallel tool use.* That conclusion would have been false, reproducible, well-controlled on every
axis we knew to control, and extremely publishable.

The two files are matched on parameters, architecture, quant recipe, packager, tensor count, block
structure and byte count to within 3.4 KB. Every axis this project has learned to match was
matched. The instrument still would have measured the template.

This is `AFM-39`'s shape again -- a false model-failure is cheaper to produce than a false success --
and it adds a new layer to the list: **the chat template's whitespace is part of the instrument.**
Before any two models are compared on tool use, round-trip each one's rendered tool call against
the parser it will be read by, and report the result. It costs one `/apply-template` call.

## Escalation with token budget, and a hard 500

The corruption **rate** does not depend on `max_tokens`; the corruption **size** does, because
`until()` compiles to a permissive GBNF rule that never constrains the model to stop. 10 seeds per
cell, same two-tool prompt:

| `enable_thinking` | `max_tokens` | HTTP 500 | corrupt | clean | longest argument |
|---|---:|---:|---:|---:|---:|
| false | 400 | 0 | 6/10 | 4 | 1,245 |
| false | 1200 | 0 | 6/10 | 4 | **3,830** |
| true | 400 | 0 | **8/10** | 2 | 2,116 |
| true | 1200 | 0 | **8/10** | 2 | **7,556** |

Thinking mode costs ~2 more corrupt turns in 10 (8/10 vs 6/10, n=10 per cell -- suggestive, not
established) and roughly doubles the longest argument. **Both matter for argus, which runs with
thinking on.**

At a large enough budget the run-on stops being silent. One request during development produced:

```
HTTP 500: Failed to parse tool call arguments as JSON:
  parse error at line 1, column 2684: syntax error while parsing value -
  invalid string: missing closing quote
```

The argument had swallowed **26 chained `<tool_call>` blocks** -- the model inventing search terms
(`budget`, `financial report`, `expenses`, `forecast`, `payroll`, `cash flow`, ...) because nothing
told it the first argument had ended.

**The quiet failure is the dangerous one.** A harness with a generous `max_tokens` gets a loud 500
it cannot miss. A harness with a tight cap gets a corrupted argument behind HTTP 200 -- which
scores.

### This error string is shared by an unrelated mechanism

`scrapebench/QWOPUS_RUNAWAY_ROOT.md` (08-01) reports the identical
`missing closing quote` 500 from a genuine **model** runaway: 43,161 characters, **zero** tool-call
markers inside the argument, 66.1% of it the token `_inner` repeated 4,754 times. Checked on
2026-09-22 against that receipt's preserved transcript; the parser hypothesis was raised and
falsified there.

Both mechanisms end in a truncated JSON string, so both surface as `missing closing quote`. **The
message names the symptom, not the cause.** To tell them apart, look inside the argument: folded
`<tool_call>`/`<function=`/`</parameter>` markers mean the parser concatenated real calls; a single
degenerate payload with none of them means the model failed to stop.

## Relation to llama.cpp#26763 -- what is new and what is not

**Not new:** the mechanism. #26763 (2026-08-08) identified the hardcoded `"\n</parameter>\n"` in
`common_chat_params_init_qwen3_coder`, quoted the same three lines, dumped the derived grammar, and
described the same run-on-argument symptom. Everything in the "Mechanism" section above is a
re-derivation of that report. Credit belongs there.

**The maintainer closed it as "Not a bug"** (aldehir, 08-09):

> The leading `\n` is required to ensure we capture the correct amount of blank lines in long-form
> string content. Without it, it's ambiguous. It seems like a problem with your fine-tune, which I
> have no interest in supporting if it (a) uses an existing template format and (b) does not align
> with the base model's behavior w.r.t tool calls.
>
> If you can show this happens on the official model with one of its popular quants, the
> recommended sampling options, and without prompting it to misbehave, I'll reconsider.

The reporter's case was a model that *occasionally sampled* `value</parameter>` instead of
`value\n</parameter>` -- sampling variance against a template that renders the newline correctly.
A follow-up (DilanRG, 08-12) offered stock Qwen3.6-35B evidence and was deflected to an Open WebUI
`reasoning_content` round-trip bug, which is a fair objection to that particular report.

**What this adds, stated narrowly:**

1. **Deterministic, not occasional.** MiMo's template *never* renders the newline form. This is not
   a model sometimes missing a terminator; it is a template whose rendered output matches **zero of
   five** required literals, every time. The round-trip table is deterministic and needs no reps.
   That makes it a different class of evidence from a sampling-variance report.
2. **It meets the stated bar, on the facts.** Official first-party model (Xiaomi's own release, not
   a community merge), a popular quant (bartowski Q8_0, byte-verified), the vendor's own
   `generation_config.json` sampling, and a benign two-step request with no jailbreak or
   misbehaviour prompting.
3. **The matched-pair control** (Ornith 0/30 vs MiMo 6/10 at 3,424 bytes apart) is new, and it
   makes a different argument than #26763 made. #26763 argued *agents break*. This argues
   **benchmarks silently lie** -- which is a harm the maintainer's framing does not cover, because
   it does not require anyone's template to be "correct."

**Where aldehir's objection still lands.** Criterion (b) -- "does not align with the base model's
behavior w.r.t tool calls" -- **is true of MiMo.** Its base is Qwen3.5-9B, which renders the
newline form; MiMo diverges from it on exactly this whitespace. A maintainer could consistently
apply the same reasoning and close this too, and would not be obviously wrong to do so: the
defect is arguably Xiaomi's.

**The argument that does not depend on whose fault the template is:** llama.cpp renders this
template with its own bundled minja, then fails to parse what it itself just rendered, and reports
HTTP 200 with a corrupted argument rather than an error. Whatever the right fix (loosen the parser,
tighten the `chat.cpp:1213` fingerprint so a compact-dialect template is not claimed by this
parser, or refuse the template at load), **silent corruption is the wrong failure mode.** That
point is about llama.cpp's behaviour, not about MiMo's template, and it is the only framing worth
raising upstream.

**Status of the code as of our tree** (`58367713a`, 2026-09-21, ~6 weeks after #26763 closed): the
three lines are unchanged. Last touches to `common/parsers/qwen3-coder.cpp` are `0bec16e38`,
`790cf51aa`, `acecd5603`, `895c045fd` -- none of them this.

## Caveats

- **`min_p` is not specified by MiMo's card.** `generation_config.json` gives temperature 0.6,
  top_k 20, top_p 0.95 and is silent on `min_p`, so llama.cpp would supply 0.05. It is pinned to 0.0
  here and that choice is ours, not the vendor's. (AFM sampling checklist item 3.)
- **These numbers are not comparable to any argus result we hold.** Every argus figure was taken at
  temp 1.0; this ran at the vendor's 0.6. That is the cost of the standing "vendor sampling only"
  decision, and it means a MiMo argus arm cannot be compared against the existing 27B arms without
  re-running those at their own vendor settings.
- n=10 per cell. The 6/10 and 3/10 figures have wide intervals; what is solid is 0/10 vs non-zero,
  and the round-trip table, which is deterministic and needs no reps.
- **Multi-turn is still untested.** A planned multi-turn probe was abandoned when the 500 above
  killed the script; the 2x2 above is single-turn. Feeding a corrupted call back as history is
  plausibly worse and is unmeasured -- do not assume either way.
- The thinking-mode delta (8/10 vs 6/10) is n=10 per cell. Directionally consistent across both
  budgets, but two turns in ten is not a separated effect.

## What this blocks

Any agentic harness that offers MiMo more than one tool and lets it call two at once will silently
lose ~60% of its multi-call turns, with the first tool receiving markup as an argument. For argus
specifically: **items that need one call per turn are safe; items that need two are not.** The
corpus must be checked for multi-call turns before a MiMo arm means anything.
