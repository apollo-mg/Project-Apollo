# Predictions — does `-fa on` change results on sm_60? (Puzzle-75B Q2_K, 4×P100)

Logged 2026-07-30 **before** the run. Decides whether the Puzzle quant ladder can mix FA
settings across rungs, or must be re-run.

## Why this matters

The two completed ladder cells (`q2_on` 91.7 %, `q2_off` 66.5 %) ran with **`-fa off`**. The
iq4 and q4 rungs OOM'd with `-fa off` and **only load with `-fa on`**. If we simply continue with
`-fa on`, every cross-rung comparison is confounded with a change of attention implementation —
the ladder would no longer isolate quantisation, which is its entire purpose.

Q2_K (29.3 GiB) is the one quant that fits **both** ways, so it can answer this directly.

## Design

`llama-perplexity` on wikitext-2, `-c 2048 --chunks 32`, `-ngl 99 -sm layer -ts 1,1,1,1`,
default f16 KV (matching the ladder's server config), `build_puzzle` (carries the sm_60 fp32
carve-out).

- **Base:** `-fa off` → writes the `.kld` reference (the setting the completed cells used)
- **Test:** `-fa on` → scored against that base

Instrument is **median KLD + top-token agreement**, not perplexity. We have a receipt
(`Instrument_Disagreement_PPL_vs_KLD.md`) where PPL inverts the ladder ordering outright and
rates the most-damaged quant as best, so PPL cannot settle this.

## Decision rule — fixed in advance

The smallest quantisation step in our reference Qwen ladder is **Q8_0 vs BF16 = 0.000103 median
KLD** (same-top 99.197 %). For FA on/off to be safely mixable across rungs, its effect must be
**clearly negligible against the effect being measured**:

| FA on-vs-off result | verdict |
|---|---|
| median KLD **< 1e-5** and same-top **≥ 99.5 %** | **safe to mix** — an order of magnitude below the smallest quant step |
| median KLD 1e-5 – 1e-4, same-top 99.0–99.5 % | **borderline** — comparable to a Q8-vs-BF16 step; re-run q2 with `-fa on` |
| median KLD **> 1e-4** or same-top **< 99 %** | **must re-run everything with `-fa on`**; and it is a finding in its own right |

## Predictions

| id | claim | confidence |
|---|---|---|
| **P-FA1** | NOT bit-identical — median KLD > 0 | **0.97** |
| **P-FA2** | median KLD < 1e-4 | **0.65** |
| **P-FA3** | same-top ≥ 99.0 % | **0.60** |
| **P-FA4** | Falls in the **"safe to mix"** band (<1e-5 and ≥99.5 %) | **0.40** |
| **P-FA5** | Server loads and completes both passes without OOM at 2048 ctx | **0.90** |

**P-FA1 is near-certain by construction.** Flash attention is a different algorithm — tiled with
online softmax rescaling — so it reorders floating-point reductions relative to standard
attention. Exact equality is not on the table; only magnitude is in question. This is the same
mechanism upstream cited for MTP ("different kernels for different batch sizes"), just triggered
by a different switch.

**P-FA4 is only 0.40 because Q2_K is the worst case for this.** At ~2.5 bpw the logit
distribution is full of near-ties — we measured a flip margin of 0.03125 at the 99.25th
percentile on a comparable quant. Tiny numerical perturbations flip more tokens at Q2 than they
would at Q8, so if any rung is going to show FA sensitivity, it is this one. That cuts both ways:
a clean result here is strong evidence for the whole ladder.

## Scoring

Score honestly on completion. If the verdict is "must re-run", say so plainly — the 20 hours
already spent on the q2 cells are sunk, and preserving them is not a reason to accept a
confounded ladder.
