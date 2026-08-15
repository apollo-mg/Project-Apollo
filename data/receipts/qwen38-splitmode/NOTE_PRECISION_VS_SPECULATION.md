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
