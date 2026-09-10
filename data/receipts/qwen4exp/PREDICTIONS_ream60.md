# Pre-registered — is REAM-60Pct lobotomised?

Registered **2026-09-02**, before the model finished downloading.

## What is being tested

`mradermacher/Qwen3.8-Flash-Next-REAM-60Pct-i1-GGUF` @ **i1-Q2_K, 56.62 GiB** — Flash-Next with
experts pruned to ~60 %, then imatrix-quantised.

Header read via a 16 MiB range request, before download:

| tensor group | full UD-Q2_K_XL | REAM-60Pct i1-Q2_K |
|---|---|---|
| `per_layer_token_embd` | 26.82 GiB | **26.82 GiB** (untouched by pruning) |
| `ffn_down_exps` | 21.09 | **12.69** (−40 %) |
| `ffn_gate_exps` | 10.91 | 7.40 (−32 %) |
| `ffn_up_exps` | 10.91 | 7.40 (−32 %) |
| total | 73.4 | 56.6 |

## Control

The **unpruned** `Qwen3.8-Flash-Next-UD-Q2_K_XL` already on `.194`, same server flags, same
prompts, same sampling. Both are ~2-bit-class, so pruning is the dominant difference — though not
the only one: Unsloth's UD recipe protects `ffn_down_exps` at IQ4_NL while mradermacher's does not,
so the pruned build is also quantised harder on that group. **Two lossy operations stacked on the
tensor group our own stacking receipts flag as the risky place to stack them.**

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | loads and produces grammatical text | 0.90 |
| P2 | correct on simple factual recall (capital of France etc.) | **0.80** |
| P3 | survives multi-step arithmetic/logic without collapsing | **0.55** |
| P4 | **no** degenerate repetition (`////`, loops) in 5 prompts | 0.70 |
| P5 | measurably worse than the unpruned control on the same prompts | **0.75** |
| P6 | usable enough to be worth the 16.8 GiB saving | **0.40** |

## Reasoning

**P2 high, P3 much lower.** Expert pruning removes capacity unevenly — routing sends different
tokens to different experts, so damage shows up on inputs whose experts were dropped. Common
factual recall is likely served by heavily-used experts that survive pruning; multi-step reasoning
touches more of the routing space and has more chances to hit a hole.

**P6 at 0.40** because the saving buys less than it appears: **the PLE is untouched at 26.82 GiB**,
so the pruned model is still 56.6 GiB, and the VRAM-residency win depends on the experts fitting,
not the file shrinking.

## Falsifier

If it is coherent on facts and holds up on multi-step reasoning with no repetition, then 40 %
expert pruning on this architecture is nearly free, which would be a genuinely useful result and
should be reported as such.
