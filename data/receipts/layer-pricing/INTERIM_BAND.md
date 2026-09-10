# fp16->t8 layer-pricing band — COMPLETE, 32 of 32 cells

Qwen3.8-27B UD-IQ4_XS | .194 GPU0+1 (NUMA node 0) | buun `7d30a7244` build_sm60_new
`-c 4096 --chunks 8 -sm tensor -fit off -ct vbr --vbr-floor t8 --vbr-vram 64M`
`GGML_CUDA_ALLREDUCE=internal` | 1063 MHz / 150 W | base = `base_f16.dat`

Each cell = one-step `VBR_DEGRADE_ORDER` demoting exactly one (layer, side) to t8,
byte-identical to the anchor otherwise. Layers 3,7,...,63 x {k,v} = 32 cells.

**Envelope:** `first=2048`, so every scored position sits at **2–4k of KV depth**. This is a
shallow-context table. Our own VBR fidelity run showed depth changes behaviour (f16
confabulation 3/24 → 1/24 going from 0 to 29k), so nothing here extends to long context (AFM-24).

## The null is not zero — and it had to be measured, not assumed

`anchor_selfcheck.bin` is fp16 vs the fp16 base. True KLD is **exactly zero** at every
position. Measured: mean -1.200e-07, median -4.157e-10, range -7.13e-05 … +6.10e-05,
**50.6% negative**. Cells show the same 48.9% negative fraction and the same -7.2e-05 floor.

This is GPU run-to-run nondeterminism (reduction order / atomics), not estimator error:

- **Per-position KLD values are unusable here.** The signal (~1e-6 mean) is ~70x smaller than
  one position's noise. Only chunk-level aggregates survive.
- Any metric touching the tail is invalid: `trim99` returned a *negative* mean and `log1p`
  went NaN, both purely from noise.

## The SE trap — this inverted the headline

There are two different SEs and using the wrong one inflates every z-score ~8x:

| | SE of the 8-chunk mean |
|---|---|
| null (GPU nondeterminism only) | 7.8e-08 |
| **median cell** (also carries chunk-dependent quantization variance) | **6.1e-07** |

Cells are **7.9x noisier than the null**. A first pass here applied the null's SE to the
cells and reported "12/12 clear at z = 9.4–27.8". That was wrong. Corrected below.

## [1] The price is real but weak — 22/32

Against each cell's **own** SE, 22 of 32 clear the null individually at 95%.

## [2] K costs more than V — in 15 of 16 layers. The 16th is the interesting one.

The layer is the replication unit (the same 8 text chunks recur in every layer, so pooling
16 x 8 as 128 independent deltas is pseudoreplication).

**Pre-registered test, all 16 layers: mean K-V = +3.921e-07, t = 2.49 on 15 df, p = 0.0251,
sign 15/16.** That is the number that counts.

It is dragged down by a single layer, and that layer is not noise:

| | layer 63 | the other 15 |
|---|---|---|
| K | 4.018e-07 | — |
| **V** | **2.093e-06** — the most expensive cell in the band | — |
| K-V | **-1.691e-06** | +5.310e-07 (t=6.65, p=0.00001, sign 15/15) |

`63v` is the **highest-confidence measurement in the whole sweep**: z = 14.88 against the null,
the tightest SE of any cell (1.49e-07), and **8 of 8 chunks agree** (paired K-V = -1.69e-06
+/- 8.4e-08, t = -20). Whatever else is uncertain here, this is not.

**Layer 63 is the last full-attention KV layer, and blk.64 is the MTP head.** A uniquely
sensitive V cache in the final layer, feeding the head, is mechanistically plausible — but that
is a *post-hoc* reading of a discovered outlier, not a tested claim. It needs its own
confirmation, and the obvious controls are a non-MTP model and the same band on Qwen3.6.

**Do not quote the 15-layer figures as the result.** Excluding layer 63 because it is
inconvenient is how false findings are made. The 15-layer numbers appear above only to show
what the outlier is being contrasted against.

## [3] The fine price table is not obtainable — gate FAILS

**`rho_half` = 0.591 +/- 0.090 over all 35 distinct 4/4 chunk splits, range [0.384, 0.730].**
Gate **0.90**, stated here because no threshold is recorded in METHODOLOGY
(`OUTLINE_lowbit_methodology.md` is an article outline and has no §6).

Median adjacent gap is **0.18 cell-SE**. Closing it to 3 SE needs ~2250 chunks/cell: **~19 h
per cell, ~615 h for 32 cells.** The fp16->t8 per-(layer,side) price is **not obtainable at any
reasonable cost on this instrument.**

## What this means practically

An earlier draft of this file suggested the band might reduce to a single **K/V asymmetry
constant**, making a per-model scan unnecessary. **Layer 63 kills that in its simplest form.**
A constant would be wrong, and wrong by 3.2x in the opposite direction, exactly at the layer
whose V cache is most expensive in the entire model. Any allocator using a flat K/V rule would
demote the single most sensitive unit first.

What survives as a cheap-scan hypothesis is weaker and more specific: **K > V generally, with
the terminal layer(s) special-cased.** Whether "terminal" means "last" or "adjacent to the MTP
head" is exactly what the Qwen3.6 / non-MTP control would separate.

## Standing

Next experiment is **not more chunks**. Same band at a *large* transition (fp16->t4 or t2),
where effect/noise is far better, asking:

1. is the ranking **transition-invariant**? If yes, a table comes cheap from one big transition.
2. does **K > V** hold there, and does **layer 63 still invert**?

Then the same band on **Qwen3.6** (no MTP head in the same position) to test whether the
layer-63 inversion is about depth or about the head.

Analyzer: `analyze_band.py`.
