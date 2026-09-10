# PREREG — the usable-context ceiling is set by the ENTRY tier, not the floor

**Written 2026-09-08 before the run.** Scored honestly, misses included.

## The claim

VBR enters at f16 and degrades under pressure. The reset message names the cost directly:

> `vbr reset: … dropping the prefix; the full re-prefill re-enters at the entry tier`

If that is the operative mechanism, then a config is stable when the **whole requested context
fits at the entry tier**, because VBR never faces pressure it cannot absorb and therefore never
resets. The floor tier governs steady-state footprint; the **entry** tier governs recovery.

**Predicted rule:**

```
usable context  ≈  KV budget ÷ f16 bytes-per-token
```

`Qwen3.8-27B` is **64 KiB/token at f16** — 16 of 65 layers carry KV, `head_count_kv 4`,
`key/value_length 256` (`gguf-librarian/RESULT_DIRK_GSQ_RCO_HYBRID.md`). A dense reading gives
256 KiB/token and is wrong by 4×.

## The grid

Measured KV budgets, `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp`, no MTP, RX 9070 XT
(`RESULT_MTP_VRAM_COST.md`):

| context | f16 cost | KV budget | ratio | prediction | status |
|---:|---:|---:|---:|---|---|
| 32,768 | 2,048 MiB | 5,410 | **0.38** | stable | **observed 44/61 (with MTP)** |
| **65,536** | **4,096 MiB** | **5,410** | **0.76** | **stable** | **TO RUN** |
| **131,072** | **8,192 MiB** | **5,384** | **1.52** | **thrashes** | **TO RUN** |
| 262,144 | 16,384 MiB | 5,256 | **3.12** | thrashes | **observed: 12 pass / 11 infra at task 23** |

**Predicted boundary: ratio 1.0 ≈ 84,000 tokens**, sitting between the two arms to be run.

## Conditions

Identical to `qwen38_262k_nomtp` except `-c`: `buun-llama-cpp/build_rocm` `3823c9eb6`,
`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`, `-ngl 99 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr
--vbr-floor t2 --vbr-vram auto --reasoning-effort medium --min-p 0`, **no MTP** (removes the
2.1 GB confound), `hermesbench --all --toolsets all --timeout-overhead 300`.

VRAM sampled every 20 s throughout, as in the 262k run.

## Predictions

| # | prediction | conf |
|---|---|---:|
| E-1 | **64k is stable**: budget-exceeded ≤ 2 for the whole run, and it does not enter a non-recovering cascade | 0.70 |
| E-2 | **128k thrashes**: budget-exceeded ≥ 5, INFRA_ERROR ≥ 25% of completed tasks | 0.65 |
| E-3 | 64k passes materially more tasks than 128k (≥ 10 more of the first 30) | 0.65 |
| E-4 | VRAM is flat in both (drift < 500 MiB over the run) — the failure is pricing, not a leak | 0.85 |
| E-5 | The **ratio**, not the absolute context, orders the outcomes: 0.38 ≥ 0.76 > 1.52 ≥ 3.12 in stability | 0.60 |

**If E-1 and E-2 both hold, the rule is supported and the boundary is bracketed to 64k–128k.**
If 64k thrashes, the entry-tier account is wrong and the ceiling is lower than the arithmetic
predicts for some other reason. If 128k is stable, the boundary is above 1.0 and the rule needs
a coefficient rather than being exact.

## What would make this quotable rather than suggestive

One model, one card, one floor tier. The rule is stated in terms of measurable quantities
(`KV budget`, `f16 bytes/token`) so it is portable in principle, but a second model or a second
card is what would establish it. **Do not publish it as a law from two arms.**

## Stopping rule

One pass each, 64k then 128k, scored together. Interim looks may abort only.
