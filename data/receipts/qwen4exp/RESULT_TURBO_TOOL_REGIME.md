# The tool-calling regime, not TURBO, is what collapses the thinking

**2026-09-03.** `.194`, 2x P100 sm_60 @ 150 W / 1063 MHz. Same models, same build, same sampling,
same `reasoning_effort: medium` as [RESULT_TURBO_THINKING_MEDIUM.md](RESULT_TURBO_THINKING_MEDIUM.md).
**The only change is a `tools` array plus `tool_choice: auto` in the request.**

Prompted by HF discussion #7 on the model repo, where users report the opposite of our measurement:

> rdent27: *"This is doing 90% [one sentence of thinking] --> [tool call]."*
> xvcy3w: *"Overthinking is gone, very intelligent and much faster."*

Our chat-regime measurement said TURBO thinks **2.52x MORE** than stock. Both cannot be right about
the same thing -- so they are not about the same thing. rdent27 names the difference himself: tools.

## Result — `reasoning_content` characters, tools present

| prompt | turbo | control | ratio | turbo call | control call |
|---|---|---|---|---|---|
| weather | 141 | 140 | 1.01x | `get_weather` | `get_weather` |
| read_file | 95 | 81 | 1.17x | `read_file` | `read_file` |
| calculate | 138 | 97 | 1.42x | `calculate` | `calculate` |
| web_search | 146 | 128 | 1.14x | `web_search` | `web_search` |
| get_time | 175 | 106 | 1.65x | `get_time` | `get_time` |
| **TOTAL** | **695** | **552** | **1.26x** | 5/5 | 5/5 |

Median ratio **1.17x**. Both models emitted the correct tool call on 5/5, `finish=tool_calls`,
zero content characters — pure dispatch.

## The finding

**rdent27's observation is real, and it is not TURBO.**

| regime | turbo think | control think | turbo/control |
|---|---|---|---|
| chat (no tools) | 17,489 | 6,952 | **2.52x** |
| tools present | 695 | 552 | **1.26x** |
| **collapse factor** | **25.2x** | **12.6x** | |

Presenting a tool schema cuts thinking by **25x on TURBO and 12.6x on stock Qwen3.8-27B**. A
one-sentence thought followed by a tool call is what *this whole model family* does when tools are
in scope. Users are attributing to the TURBO merge a behaviour the stock model exhibits just as
strongly. Their *experience* is accurate; the *attribution* is not.

Two honest nuances in TURBO's favour:

- **TURBO responds more to the regime** (25.2x vs 12.6x collapse). It has more excess to shed.
- **In the tool regime the practical gap nearly vanishes.** Completion tokens: turbo 330 vs control
  306 = **1.08x**. For agentic work the choice is ~8% -- effectively a wash, versus **1.82x** in
  chat. So someone doing purely tool-driven work would not feel TURBO's chat-mode verbosity at all.

That is the reconciliation: the commenters are running the regime where the difference does not
show up, against a baseline (in rdent27's case an unnamed "thinkingcap tune" he found excruciating)
that is not the stock model.

## What this does NOT show

- **TURBO still never beats stock.** 1.26x more thinking with tools, 2.52x without. The card's
  claim -- "reduces thinking tokens by 1/2 to as high as 1/10", "median reduction: 2/3 roughly",
  "extends across all three modes of operation" -- is not reproduced in either regime.
- **These prompts are trivially tool-shaped.** Each maps to one obvious tool with no ambiguity, no
  multi-step planning, no tool *results* to interpret. Real agentic work has all three, and the
  collapse is likely less complete there. This bounds the claim; it does not measure agentic work.
- **The merge-vs-TURBO confound is untouched.** Still "DavidAU's merge vs stock Qwen3.8-27B".
  The card names the missing control: `Qwen3.8-27B-Cold-Fusion-GAIN-V1.1`, the non-TURBO base of
  the same merge.
- **MTP variant unmatched.** We ran `...MAX-MTP-Q4_K_S`; the repo also ships non-MTP and LOW-MTP
  builds and the commenters do not say which they used.
- **K=1, 5 prompts.**

## Provenance (checked, because DavidAU's metadata is unreliable)

Our file is `Qwen3.8-27B-TurboFCFusion-735-882-Here-Uncen-NEO-CODER-MAX-MTP-Q4_K_S.gguf`,
17,537,488,416 bytes, matching the repo listing's 17.5 GB entry exactly. But its embedded
`general.name` is **"Qwen3.8 27B Brainwaves NM HERETIC BR LOA1"** and `general.finetune` is
**"Brainwaves-NM-HERETIC-BR-LOA1"** -- an unrelated merge. **Filename and byte size are the only
reliable handles on this publisher's models**; embedded metadata cannot identify them. Same family
of problem as [gguf-label-is-not-a-spec].

Both chat templates were dumped and compared: each resolves `reasoning_effort: medium` to an empty
instruction string, so the medium arms were genuinely uninstructed in both models. TURBO carries an
older template revision (no multi-system-message merging; raises on `high` instead of silently
mapping it to `xhigh`), which does not affect these runs.
