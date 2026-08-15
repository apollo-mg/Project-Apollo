# The precision-vs-speculation trade has a threshold, and it is just the size ratio

**Written 2026-08-15, before the arms that test it finished.** Prompted by
`mlx-dspark` (@_ARahim_), reporting ~3x faster decoding for Qwen3.8-27B on Apple Silicon
and concluding that **the 8-bit model with a drafter now decodes faster than the plain
4-bit model**. That is a real and useful claim, and it generalises to a one-line rule.

## The rule

Decode is memory-bandwidth bound, so throughput runs roughly inverse to weight bytes. A
higher-precision model plus speculation beats a lower-precision model alone exactly when

> **speculative multiplier > size ratio**

Nothing else enters at leading order. So the interesting question is never "is speculation
fast" — it is whether the multiplier on *your* hardware clears the bar *your* two quants set.

## On this fleet the answer differs by GPU

`Qwen3.8-27B`, unsloth files: `UD-IQ3_XXS` 11,913,559,104 B vs `Q6_K` 22,884,408,288 B.

**Size ratio: 1.921x.** So Q6_K needs a >1.92x speculative multiplier merely to *match*
IQ3_XXS running with no speculation at all.

| hardware | measured MTP multiplier | vs the 1.92x bar | verdict |
|---|---|---|---|
| 2x P100, `.73` (Pascal) | **1.52x** | 0.79x | **falls short** |
| RX 9070 XT (RDNA4) | **2.05x** | 1.07x | **clears it, barely** |
| Apple Silicon, `mlx-dspark` (reported) | ~3.3x | ~1.7x | clears comfortably |

**The same trade flips sign between two GPUs in the same house.** On Pascal, spending the
VRAM on Q6_K and turning MTP on is predicted to lose to simply running IQ3_XXS. On RDNA4 it
is predicted to win by 7 %, which is inside the margin where file-size ratio and quant choice
decide it rather than the principle.

This is why the Apple result is not portable as stated. It is not that Apple Silicon is
special — it is that **3.3x clears a 2x bar and 1.52x does not.**

## Sealed prediction

Testable at zero extra compute from arms already running on `.73`: the packager A/B produces
`Q6_K` with MTP on and off, and the split x MTP ladder produces `UD-IQ3_XXS` with MTP off,
both under `-sm layer` on the same node.

| # | prediction | conf |
|---|---|---|
| S1 | On `.73`, `Q6_K` + MTP is **slower** than `UD-IQ3_XXS` with MTP off | 0.75 |
| S2 | `Q6_K` MTP-off throughput lands within 15 % of `8.585 / 1.921 = 4.47` t/s | 0.65 |
| S3 | The `Q6_K` MTP multiplier **exceeds** the `IQ3_XXS` multiplier of 1.52x | 0.60 |

S2 tests the bandwidth-bound assumption the whole rule rests on. If measured `Q6_K` MTP-off
throughput is far from what the size ratio predicts, then throughput is not tracking bytes
here and the rule needs a correction term before anyone applies it.

S3 is the interesting one: a `Q6_K` target has a `Q6_K` draft head and a less-damaged body,
so drafts should be accepted more often than `IQ3_XXS`'s. If the multiplier rises enough with
precision, the bar becomes easier to clear at higher precision — which would make the trade
*self-reinforcing* rather than a fixed threshold, and S1 could survive as a Pascal fact while
failing as a general rule.

## RESULTS — S1 and S2 falsified. The rule was right; the bar was wrong.

Measured on `.73`, `-sm layer -ts 1,1`, 7 of 8 arms complete (`bart_off_2` still running):

| file | MTP off | MTP on | multiplier | draft acceptance |
|---|---|---|---|---|
| bartowski `Q6_K` | 7.87 | 14.48 | **1.840x** | 70.70 % |
| unsloth `Q6_K` | 7.69 / 7.68 | 13.97 / 13.96 | **1.817x** | 71.50 % |

| # | prediction | outcome |
|---|---|---|
| S1 | `Q6_K`+MTP slower than `IQ3_XXS` no-MTP | **FALSIFIED** — 13.96 vs 8.585, it is **1.63x faster** |
| S2 | `Q6_K` MTP-off within 15 % of 4.47 t/s | **FALSIFIED** — measured 7.69, off by **72 %** |
| S3 | `Q6_K` multiplier > 1.52x | **CONFIRMED** — 1.82x |

### Why S2 failed: this hardware is not bandwidth-bound

S2 was the load-bearing assumption, and it is wrong here. At 7.69 t/s on a 22.88 GB file the
decode is moving **176 GB/s against the P100's ~732 GB/s HBM2 peak — 24 % of it.** Nowhere
near saturated. Two reasons: the cards run at a **150 W cap** (fleet standing config), which
cuts compute far more than bandwidth, and **layer split is pipelined**, so only one card is
active at a time.

So the size ratio is only an **upper bound** on the throughput cost of precision, and on this
hardware it overestimates it by a factor of nearly two:

| | ratio |
|---|---|
| size, `Q6_K` / `IQ3_XXS` | 1.921x |
| **measured throughput** | **1.117x** |

### The corrected rule

> **speculative multiplier > measured throughput ratio**

not the size ratio. The size ratio is what you can compute without running anything, which is
why it is tempting, and it is only correct when decode is actually bandwidth-bound. Anyone
applying the rule from file sizes on power-limited or compute-bound hardware will conclude
they cannot afford precision when they can.

### The practical finding, which is the opposite of what was predicted

**On 2x P100, `Q6_K` with MTP beats `IQ3_XXS` without it — 13.96 t/s against 8.585 — at
roughly twice the weight precision.** The instinct that a fitting low-bit quant is the fast
choice is wrong on this hardware. It is slower *and* worse.

This validates the *shape* of the `mlx-dspark` claim on completely unrelated hardware, but
for a different reason than would be assumed: their ~3.3x cleared a bandwidth-driven bar;
1.82x clears a compute-driven bar of 1.12x. Same conclusion, different physics.

### An unplanned finding: the bigger file is the faster one

bartowski's `Q6_K` is **2.5 % larger** (23.46 vs 22.88 GB) and **2.3 % faster** (7.87 vs
7.69). Under a bandwidth-bound model that is impossible. It follows directly from the recipe:
he ships `Q8_0` x120 against unsloth's x48, and `Q8_0` — a 32-element block with an fp16
scale — is markedly cheaper to dequantise than `Q6_K`'s 256-element superblock with packed
6-bit values and sub-scales. **On compute-bound hardware the cheaper kernel wins despite the
extra bytes.** Suggestive, not established: the two files differ in more than that one axis.

### Caveat on the comparison

The `IQ3_XXS` 8.585 baseline came from a different harness (`mtp_ab.py`, single GPU) than the
`Q6_K` arms (`mtp_pkg_ab.py`, `-sm layer`). Same prompts, same sampling, and layer split
measured 0.995x of single-GPU, so they are comparable — but the clean same-harness version
arrives with the split x MTP ladder queued behind this run, and these ratios should be
restated from it.

## One correction to how "lossless" reads

`mlx-dspark` is described as lossless. For strict-verification speculative decoding that is
**a property of the method, not an achievement**: rejected drafts are discarded, so the output
distribution is identical to non-speculative decoding by construction. It is worth stating
because it also bounds what any of these experiments can find — a worse draft head costs
speed and nothing else. None of this measures model quality, because it cannot.

(That guarantee is exact for verify-and-reject speculation. Block-diffusion methods like
DFlash denoise a masked block in place, and whether they retain the same guarantee depends on
their acceptance test — not checked here, and not assumed.)

## Limits

- One model pair, one fleet. The rule is arithmetic; the multipliers are hardware facts and
  transfer to nobody else's box.
- The 1.52x and 2.05x were measured on `UD-IQ3_XXS`, not on `Q6_K` — S3 exists precisely
  because using them for a Q6_K prediction assumes a constant multiplier across quants.
- The RDNA4 row is **not directly testable here**: `Q6_K` is 21.31 GiB against 16 GiB of
  VRAM, so measuring it would mean partial offload, which breaks the bandwidth-bound
  assumption the rule depends on. That row stays a prediction.
- No Apple Silicon on this fleet, so the `mlx-dspark` figure is quoted, not verified.
