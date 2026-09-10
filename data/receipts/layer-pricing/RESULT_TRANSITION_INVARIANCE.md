# Layer pricing is transition-specific — and one unit dominates at every scale

**2026-08-26**, `.194` GPUs 0+1 (NUMA node 0), 2× Tesla P100 sm_60, 1063 MHz / 150 W.
buun `7d30a7244` `build_sm60_new`. `Qwen3.8-27B-UD-IQ4_XS`, `-c 4096 --chunks 8 -sm tensor
-fit off -ct vbr --vbr-vram 64M`, `GGML_CUDA_ALLREDUCE=internal`. Base `base_f16.dat`.

Three complete 32-cell bands — fp16→t8, fp16→t4, fp16→t2. Each cell is a one-step
`VBR_DEGRADE_ORDER` demoting exactly one (layer, side), byte-identical to the anchor
otherwise. 96 cells total. Scripts: `kld_band.sh`, `kld_band2.sh`. Analyzer: `analyze_band.py`.

**Envelope:** `first=2048`, so every scored position sits at 2–4k of KV depth. Shallow-context
(AFM-24). The null is GPU run-to-run nondeterminism, measured — see `INTERIM_BAND.md`.

## Effect size scales as intended

| transition | mean KLD | vs t8 |
|---|---:|---:|
| fp16→t8 | 7.699e-07 | 1× |
| fp16→t4 | 1.021e-04 | **133×** |
| fp16→t2 | 7.829e-04 | **1017×** |

## [1] The per-cell ranking never becomes reproducible — even at 1000× the signal

| transition | `rho_half` (35 splits) | gap | chunks/cell for 3 SE | total |
|---|---|---|---|---|
| t8 | 0.591 ± 0.090 | 0.18 SE | ~2250 | ~615 h |
| t4 | 0.674 ± 0.131 | 0.17 SE | ~2553 | ~698 h |
| t2 | **0.743 ± 0.064** | 0.28 SE | ~923 | ~252 h |

It improves monotonically with transition size, as predicted — and still **FAILS** a 0.90 gate
at 1017× the effect. Raising the signal three orders of magnitude did not make the fine
ranking cheap, because the per-cell variance scales with it.

## [2] The ranking is NOT transition-invariant — this is the headline

Spearman between per-cell rankings:

| pair | rho | p |
|---|---:|---:|
| t8 vs t4 | +0.686 | <0.0001 |
| t4 vs t2 | +0.657 | <0.0001 |
| **t8 vs t2** | **+0.247** | **0.17** |

Adjacent transitions agree. **The extremes do not.** The ranking *drifts* as damage grows, so
a table measured at one tier does not transfer to a distant one.

**A "layer price table" is a property of (model, transition), not of the model.** The
cheap-scan hypothesis — measure once at a big transition, reuse everywhere — is dead in that
form. Auto-generating a table on encountering an unknown model would have to be repeated
per transition, which is exactly the cost it was supposed to avoid.

## [3] K > V is FALSIFIED as a general rule

| transition | mean K−V | t (15 df) | p | sign |
|---|---:|---:|---:|---|
| t8 | +3.921e-07 | 2.49 | **0.025** | 15/16 |
| t4 | +2.071e-05 | 0.68 | 0.51 | 13/16 |
| t2 | +1.936e-05 | 0.07 | 0.95 | 12/16 |

Significant only at the **smallest** transition, and gone by t4. An earlier draft of
`INTERIM_BAND.md` floated a "K/V asymmetry constant" as a cheap substitute for a scan. That is
now doubly dead: layer 63 inverts it, and it does not survive a larger transition at all.

## [4] What DOES hold: layer 63's V cache, at every scale

`63v` is the **single costliest cell in all three bands** — rank 1 at t8, t4 and t2, across a
1017× range of effect size. And K−V at layer 63 is negative (V costlier) throughout:

| transition | layer-63 K−V |
|---|---:|
| t8 | −1.691e-06 |
| t4 | −4.185e-04 |
| t2 | −4.163e-03 |

At t8 this was one outlier in one band and read as post-hoc. It now reproduces at 133× and
1017× the effect. Layer 63 is the **last full-attention KV layer**; `blk.64` is the MTP head.

**This is the actionable result.** An allocator does not get a usable per-layer table, but it
should never demote the terminal layer's V cache early — that unit is the most expensive one
in the model at every transition tested.

**Still untested:** whether "terminal" means *last layer* or *adjacent to the MTP head*. The
control is the same band on a model without an MTP head in that position.

## Top-5 costliest cells per band

```
t8: 63v 11k 15k 7k  51k
t4: 63v 27k 31k 51k 19k
t2: 63v 51k 27k 31k 43k
```

`63v` is first everywhere. Below it the order reshuffles — which is [2] in concrete form.
