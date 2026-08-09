# Pre-registration — RDNA4 GEMM throughput by dtype

Written **before** any sweep was run, after a single exploratory measurement that
produced the question. Hardware: RX 9070 XT (gfx1201, RDNA4), 15.9 GiB.
Stack: torch 2.10.0.dev20250926+rocm6.3 (HIP 6.3.42131) on a ROCm 7.2.4 system.

## What prompted this

One ad-hoc run, K=1, clocks unrecorded, shape 4096³ only:

```
fp32           2.5 TFLOP/s
fp16          13.3 TFLOP/s
bf16          39.0 TFLOP/s      <-- 2.9x fp16, on hardware that has both
fp8_e4m3fnuz 122.5 TFLOP/s
copy bandwidth ~585 GB/s (91% of ~645 spec)
```

fp16 and bf16 should be near-identical on RDNA4. They are not. That is the question.

## Predictions (logged before the sweep)

| ID | Prediction | Confidence |
|---|---|---|
| **P1** | The fp16<bf16 gap reproduces across **≥3 distinct shapes** — it is not a 4096-only kernel-tuning artifact | 0.85 |
| **P2** | Switching the BLAS backend (rocBLAS ↔ hipBLASLt) moves fp16 throughput **>1.5×** | 0.60 |
| **P3** | fp16 reaches **within 20% of bf16** under at least one configuration available on this box | 0.50 |
| **P4** | FP8 `_scaled_mm` is numerically **correct** against an fp32 reference (within fp8 tolerance), not a fast-but-wrong path | 0.75 |
| **P5** | fp32 GEMM is **below 25%** of the card's ~48 TFLOPS vector-fp32 spec | 0.70 |
| **P6** | Even bf16 at 39 TFLOP/s is **below** the WMMA peak this card should reach — i.e. the "fast" path is not at peak either | 0.65 |

Falsifying any of these is the point. P3 at 0.50 is a genuine coin-flip: it is
entirely possible this wheel has no fast fp16 GEMM for gfx1201 at all.

## Addendum — predictions for the newer-wheel re-test (logged 2026-08-09, before results)

The `rocm7.2` channel matches the system ROCm exactly (7.2.4), so it is the re-test
target. A mechanism became available after the first sweep and sharpens the guess:

**AMD's `fnuz` FP8 variants are a CDNA3-era format** (bias 8, unsigned zero). CDNA4
moved to OCP `e4m3fn` (bias 7). RDNA4/gfx1201 is neither, but if its kernels implement
**OCP `e4m3fn` semantics** while the `rocm6.3` wheel only exposes `float8_e4m3fnuz`
— it does; `e4m3fn` raises *"only supported for ROCm 6.5 and above"* — then users are
forced onto fnuz data that the kernel reads with the wrong bias. 2× per operand,
**4× in the product.** That is exactly the observed constant.

| ID | Prediction | Confidence |
|---|---|---|
| **P7** | On the `rocm7.2` wheel, `float8_e4m3fn` is **available** (no ROCm-version error) | 0.80 |
| **P8** | `float8_e4m3fn` on that wheel is **numerically exact** (ratio ≈ 1.0 vs the dequantized reference) | 0.70 |
| **P9** | `float8_e4m3fnuz` on that wheel **still shows the 4×**, or is rejected outright for gfx1201 | 0.65 |
| **P10** | The fp16 < bf16 gap **persists** on the newer wheel (it is kernel selection, not a version bug) | 0.55 |

P10 at 0.55 is deliberately near a coin-flip: a year of hipBLASLt gfx1201 tuning is
exactly the kind of thing that would close it, and I have no evidence either way.

## Gates

- **G1 — clock discipline.** sclk/mclk/power recorded before and after every arm.
  If sclk varies more than 15% across arms, the comparison is DPM/thermally
  confounded and must be re-run with clocks pinned. Per
  `gpu-clock-benchmark-discipline`, receipts without clock state are not receipts.
- **G2 — correctness before throughput.** A dtype's throughput is only reported
  if its output matches an fp32 reference within that dtype's tolerance. A fast
  wrong kernel is the failure mode this campaign keeps finding; it does not get a
  free pass here because the number is flattering.
- **G3 — allocation outside the timing loop.** The measurement that started this
  had `torch.randn` inside the loop and was mostly RNG. Every timed region
  contains the matmul and nothing else.

## Known limits, declared up front

- This is a **single dev wheel** (`rocm6.3`, dated 2025-09-26) on a newer system
  ROCm. Any negative result is a claim about this build, not about RDNA4.
- The GPU is also driving the desktop, so it is not an idle bench.
- One card, K=1 architecture. This measures gfx1201, not RDNA4 generally.
