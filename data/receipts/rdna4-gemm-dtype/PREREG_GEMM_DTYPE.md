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
