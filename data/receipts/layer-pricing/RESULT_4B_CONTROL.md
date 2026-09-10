# The terminal-layer V cache is real within qwen35 — NOT a general rule

> **RETRACTION 2026-08-26.** The allocator recommendation below ("never demote the terminal
> layer's V cache early") is **withdrawn as a general rule**. A pre-registered control on
> `Llama-3.2-3B-Instruct-BF16` (28 dense KV layers) found `27v` ranked **56/56 — the cheapest
> cell of all** — with the *early layers' K caches* dominating instead. The effect holds
> within `qwen35` hybrids and inverts on a dense Llama. See `RESULT_LLAMA_3B.md`.
> Do not apply it across architectures.

**2026-08-26**, `.73` 2× Tesla P100 sm_60. buun `e332b24` `buun_vbr/build`.
`Qwen3.5-4B-Q5_K_S`, `-c 4096 --chunks 8 -sm layer -fit off -ct vbr --vbr-vram 32M`.
48 cells = 8 KV layers × 2 sides × 3 transitions. Script `4b_control/kld_band_4b.sh`.

## Why this model

On `Qwen3.8-27B`, cell `63v` — the V cache of the **last** full-attention KV layer — was the
costliest cell in all three bands across a 1017× range of effect size. But `blk.64` there is
the **MTP head**, so "terminal layer" and "MTP-adjacent" were perfectly confounded and only
one of them generalises.

`Qwen3.5-4B` breaks it: same `qwen35` hybrid family, same every-4th KV layer spacing
(3, 7, … 31 — read from `blk.N.attn_k` tensor names), 8 KV layers, and **no MTP head**
(no `nextn` key in the metadata). Its terminal KV layer, 31, is followed by nothing.

Null measured as before — fp16 vs fp16, mean −8.99e-08, SE 1.59e-07, **50.0% negative**.

## [1] It replicates. The confound is broken.

| transition | mean KLD | `31v` rank | layer-31 K−V |
|---|---:|---:|---:|
| fp16→t8 | 1.408e-06 | **2 / 16** | −2.607e-06 (V costlier) |
| fp16→t4 | 3.157e-04 | **1 / 16** | −6.601e-04 (V costlier) |
| fp16→t2 | 2.331e-03 | **1 / 16** | −6.756e-03 (V costlier) |

The terminal layer's V cache is rank 1 at two of three transitions and rank 2 at the third,
in a model with **no MTP head at all**. Combined with `63v` on Qwen3.8-27B, the effect now
holds across two model sizes, two layer counts (8 vs 16 KV layers), MTP present and absent,
and six bands.

**This is an allocator rule, not a curiosity: never demote the terminal layer's V cache early.**

## [2] K > V as a general rule stays falsified

| transition | t (7 df) | p | sign |
|---|---:|---:|---|
| t8 | 1.45 | 0.19 | 7/8 |
| t4 | 0.21 | 0.84 | 6/8 |
| t2 | 0.04 | 0.97 | 7/8 |

Not significant anywhere here. On the 27B it reached p=0.025 only at the smallest transition
and vanished by t4. The "K/V asymmetry constant" idea is dead in both models. What survives is
the *terminal layer specifically*, which is a much narrower claim.

## [3] Transition-invariance is MODEL-DEPENDENT — the 27B result does not generalise

Spearman between per-cell rankings:

| pair | Qwen3.5-4B | Qwen3.8-27B |
|---|---:|---:|
| t8 vs t4 | **+0.962** | +0.686 |
| t8 vs t2 | **+0.953** | **+0.247 (n.s.)** |
| t4 vs t2 | **+0.938** | +0.657 |

In the 4B the ranking is essentially fixed across a 1650× range of effect size. In the 27B the
extremes are uncorrelated. **Whether a table measured at one transition transfers to another
is a property of the model, not of the method** — so neither "it transfers" nor "it doesn't"
is safe to assume.

## [4] The acceptance gate PASSES for the first time

| transition | `rho_half` (35 splits) | gate 0.90 | median adjacent gap |
|---|---|---|---|
| **t8** | **0.957 ± 0.016** | **PASS** | 0.91 cell-SE |
| t4 | 0.840 ± 0.090 | FAIL | 1.26 cell-SE |
| t2 | 0.852 ± 0.068 | FAIL | 0.92 cell-SE |

The 27B never passed at any transition (0.591 / 0.674 / 0.743) and needed 250–700 h to close.
The 4B passes at 8 chunks per cell — roughly 40 minutes for the whole band.

**Mechanism — hypothesis FALSIFIED, corrected below (2026-08-26).**

The first draft of this file proposed that the 4B passes because it spreads **16 cells** over a
range the 27B packs 32 into, so obtainability would scale inversely with *cell count*. That is
wrong, and it was cheap to check: subsample the existing 27B bands down to 8 alternating
layers (16 cells, same density as the 4B) and recompute.

| band | 32 cells | two disjoint 16-cell subsets |
|---|---:|---:|
| t8 | 0.591 | 0.608 / 0.595 |
| t4 | 0.674 | 0.765 / 0.630 |
| t2 | 0.743 | 0.777 / 0.707 |

Barely moves, and nowhere near the 4B's 0.957. **Cell count is not the mechanism.**

The real difference is **per-cell signal-to-noise** — each cell's own mean over its own SE:

| band | KV layers | median cell mean | median cell SE | median z |
|---|---:|---:|---:|---:|
| Qwen3.8-27B t8 | 16 | 5.778e-07 | 2.612e-07 | 2.2 |
| Qwen3.8-27B t4 | 16 | 8.442e-05 | 1.658e-05 | 5.1 |
| Qwen3.8-27B t2 | 16 | 5.951e-04 | 9.134e-05 | 6.5 |
| Qwen3.5-4B t8 | 8 | 1.029e-06 | 1.816e-07 | **5.7** |
| Qwen3.5-4B t4 | 8 | 2.213e-04 | 2.235e-05 | **9.9** |
| Qwen3.5-4B t2 | 8 | 1.941e-03 | 2.001e-04 | **9.7** |

The 4B's cells are ~2x better resolved at every transition, and its per-cell *effects* are
larger in absolute terms despite the smaller model. Reading: **one layer of 8 is a larger
share of the KV cache than one of 16, so demoting it perturbs more.** Subsampling cannot
recover that — it changes how many cells you rank, not how well any single one is measured.

The conclusion survives in the same direction but for a precise reason: obtainability tracks
**KV layer count**, via per-cell effect size, not via the number of cells you choose to
measure. Predicted consequence: a model with ~32 KV layers should show per-cell z below the
27B's, and fail worse.

**Still confounded:** the two runs differ in quant (Q5_K_S vs UD-IQ4_XS) and split mode
(`-sm layer` vs `-sm tensor`). The prediction above is the discriminating test.


---

## Mechanism hunt — THIRD hypothesis falsified (2026-08-26)

A Q6_K band on Qwen3.8-27B, against the existing UD-IQ4_XS band (same model, same 16 KV
layers, t8, everything else matched):

| quant | median per-cell z | rho_half | top4 | `63v` rank |
|---|---:|---:|---|---:|
| UD-IQ4_XS | 2.04 | 0.591 | `63v 11k 15k 7k` | #1 |
| **Q6_K** | **1.84** | **0.572** | `11k 19v 23k 19k` | **#5** |

**Better quantization did not improve per-cell SNR** — z went slightly down. So the running
tally of falsified mechanisms is:

1. **cell count** — falsified by subsampling the 27B bands to 16 cells (rho_half barely moved)
2. **KV layer count (1/n)** — falsified by Llama-3.2-3B: 28 layers, the MOST, and z=37.4, the highest
3. **quantization level** — falsified here: Q6_K ≈ UD-IQ4_XS

**One distinction survives, and it is binary rather than graded.** The 4B's 5.2x jump was
Q5_K_S → **BF16**, i.e. quantized → *un*quantized. Q6_K → UD-IQ4_XS is quantized → quantized.
So the effect may be the presence of weight quantization at all, not its severity. Consistent
with both results; supported by one comparison. Testing it needs a BF16 27B (~54 GB, all four
P100s).

Also: `63v` fell from #1 to #5 at Q6_K, so the terminal-V finding is quant-sensitive at 27B
too — further support for the retraction at the top of this file.
