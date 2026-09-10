# FALSIFIED: there is no context ceiling. Prefix reuse is perfect at 262k, and the agent thrash has a different cause

**Date:** 2026-09-08 · **Prereg:** `PREREG_ENTRY_TIER_CEILING.md`
**Node:** RX 9070 XT · `buun-llama-cpp/build_rocm` `3823c9eb6`
**Model:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`, no MTP
`-ngl 99 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto`
**Raw:** `spark_raw/ceiling_sweep.log`, `/tmp/ceil_*.log`, probe in `ceiling_probe.py`

## The hypothesis

VBR enters at f16 and degrades under pressure; a reset re-prefills at the entry tier. So a
config should be stable while the whole context fits at f16, predicting

```
usable context ≈ KV budget ÷ 64 KiB    ≈ 84,000 tokens on this card
```

with the boundary between 64k (ratio 0.76) and 128k (ratio 1.52).

## Result — flat across a 8× context range

Four distinct prompts sharing a 10,309-token prefix, each sent twice, `max_tokens=16`.
Measurement is **server-side prefill work**: a reused prefix shows ~516 tokens, a reset shows
the full 10,825.

| ctx | f16 cost | KV budget | ratio | full prefills | reused | exceeded | resets |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 32,768 | 2,048 MiB | 5,480 | 0.37 | 1 | 7 | 0 | 0 |
| 65,536 | 4,096 | 5,410 | 0.76 | 1 | 7 | 0 | 0 |
| 98,304 | 6,144 | 5,378 | 1.14 | 1 | 7 | 0 | 0 |
| 131,072 | 8,192 | 5,384 | 1.52 | 1 | 7 | 0 | 0 |
| 196,608 | 12,288 | 5,320 | 2.31 | 1 | 7 | 0 | 0 |
| **262,144** | **16,384** | **5,248** | **3.12** | **1** | **7** | **0** | **0** |

One cold prefill (14.5 s / 10,825 tokens), then seven reuses (0.8 s / 516 tokens). **Identical
at every size.** No degradation, no resets, no budget pressure — at a ratio of 3.12.

## Prediction scoring

| # | prediction | conf | outcome |
|---|---|---:|---|
| E-1 | 64k stable, exceeded ≤ 2 | 0.70 | **HIT but uninformative** — everything was stable |
| E-2 | 128k thrashes, exceeded ≥ 5 | 0.65 | **FALSIFIED** — 0 exceeded, perfect reuse |
| E-3 | 64k passes ≥ 10 more than 128k | 0.65 | **FALSIFIED** — identical |
| E-4 | VRAM flat, no leak | 0.85 | **HIT** |
| E-5 | ratio orders the outcomes | 0.60 | **FALSIFIED** — no ordering; all six cells identical |

**The entry-tier account is wrong**, and so is the rule derived from it. Do not use
`usable context ≈ KV budget ÷ f16 bytes-per-token`; it was a plausible mechanism that the
measurement does not support.

## What this means for the deployment thrash

`RESULT_DEPLOY_CONFIG_THRASH.md` remains a correct observation and its explanation is now
**unsupported**. 262k does not inherently thrash: with a static working set it reuses perfectly.

The distinguishing variable is **prompt shape**, not context size:

| | this probe | the agent run |
|---|---|---|
| prompt across requests | fixed prefix + changing tail (**append-only**) | full conversation re-rendered each turn |
| reuse observed | 7/8 requests, 516 of 10,825 tokens | **`0/14,390 tokens reusable`** |

**Zero reuse is the tell.** A conversation that merely grows should reuse its prefix — that is
what this probe demonstrates. Zero means the prefix is being *altered*, not extended.

## The candidate cause, already documented here

`prompt-cache-prefix/FINDING.md` (2026-08-14) describes exactly this failure mode in a different
harness: volatile content placed early in the prompt invalidates everything after it, because a
prompt cache matches on a **common prefix**.

`qwen38-template/RESULT_TEMPLATE_AUDIT.md` shows Qwen3.8's template defaults `preserve_thinking`
**ON**, replaying every prior assistant turn's thinking into the prompt. If those blocks are
re-rendered, trimmed, or reordered as the conversation grows, the prefix diverges every turn and
reuse is impossible regardless of how much KV budget exists.

**Next test, and it needs no GPU:** diff consecutive rendered prompts from a saved agent trace.
If turn N+1 is not a strict extension of turn N, that is the cause, and it is a template/harness
issue rather than a VBR one. `traces/qwen38_deploy_det01/` has the material.

## Method note — the probe's own limits

- The four prompts share one prefix, so only the first request is ever cold. The wall-clock
  columns in `ceiling_sweep.log` are therefore meaningless (and were additionally corrupted by a
  `grep -oE "[0-9.]+"` that matched the digit in the word "round1"). **The server-side
  `prompt eval time … / N tokens` counts are the measurement**; they were read from the raw logs.
- `max_tokens=16` and no tools, by design — that removes generation runaways and the
  2026-08-29 tool-rename skew, both of which produce `INFRA_ERROR` in hermesbench and cannot be
  distinguished from a cache cascade there.
- One model, one card, one floor tier, one working-set size (~11k tokens). A larger working set
  might behave differently; untested.
