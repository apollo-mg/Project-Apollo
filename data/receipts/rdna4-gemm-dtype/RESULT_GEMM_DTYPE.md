# RDNA4 GEMM by dtype — both findings were a stale wheel, and that is the finding

**RETRACTION NOTICE.** An earlier version of this file reported two defects on
gfx1201: an FP8 path returning answers exactly 4× too large, and fp16 running
1.7–7.2× slower than bf16. **Both are real on the wheel measured, and both
disappear entirely on a current wheel.** Neither is a claim about RDNA4, ROCm, or
PyTorch as they stand today. The superseded numbers are kept below in full,
because the failure mode is the point.

**Hardware:** RX 9070 XT (gfx1201, RDNA4), 15.9 GiB, driving the desktop.
**Date:** 2026-08-09. Prereg: `PREREG_GEMM_DTYPE.md` (P1–P6 before the first sweep,
P7–P10 before the re-test).

## The actual result

Same card, same day, same test. Only the wheel changed.

| dtype @ 4096² | `2.10.0.dev20250926+rocm6.3` | `2.13.0+rocm7.2` | change |
|---|---|---|---|
| fp32 | 2.5 | 15.6 | **6.2×** |
| fp16 | 16.9 | **125.7** | **7.4×** |
| bf16 | 38.7 | 126.2 | **3.3×** |
| fp8 | 121.9 — **4× WRONG** | **239.8 — exact** | **2.0× and correct** |

TFLOP/s. Old wheel: median of 5, perf level pinned high. New wheel: median of 30
iterations after 10 warmup, clocks on `auto`.

**On the current wheel the card behaves exactly as it should.** fp16 and bf16 are
equal to within noise at every shape (ratios 0.98 / 0.96 / 1.00 / 1.09), and FP8 is
~1.9× the 16-bit rate, which is the hardware's designed relationship.

## Why the old wheel was wrong: a dtype trap that fails silently

`e4m3fnuz` is a **CDNA3-era AMD format** — exponent bias **8**, unsigned zero. OCP
`e4m3fn` uses bias **7**. gfx1201 implements OCP semantics.

On the `rocm6.3` wheel, `float8_e4m3fn` is **unavailable**:

```
RuntimeError: Float8_e4m3fn is only supported for ROCm 6.5 and above
```

So the only FP8 dtype a user can reach is `fnuz` — bias-8 data handed to a bias-7
kernel. Every value reads 2× high, the product 4× high:

```
got / dequantized-reference   mean 4.000000   std 7.7e-08   corr 1.0
scale_a = 0.25  ->  relative error 0.000000  (exact)
```

The control that makes this a kernel claim, not a precision claim: the same fp8
values multiplied in fp32 sit **0.037** from the fp32 reference — fp8's own
quantization cost. The kernel sat **3.0** from that same reference. Correlation 1.0
and std 1e-8: the matrix math was perfect, only the magnitude was wrong.

**Nothing errored.** Output was finite, correlated, plausible, and arrived at
122 TFLOP/s. Any FP8 workload on that stack silently got 4×-inflated activations.

**On the current wheel that trap is closed properly:** `float8_e4m3fn` works and is
*bit-exact* (ratio 1.0, std 0.0, relative error 0.0), and `float8_e4m3fnuz` no longer
returns a wrong answer — it raises `HIPBLAS_STATUS_NOT_SUPPORTED`. The silent wrong
path became a hard error. That is the correct fix and it is already shipped.

## Prediction scoring — 6/10

| ID | Prediction | Conf | Outcome |
|---|---|---|---|
| P1 | fp16<bf16 gap reproduces across ≥3 shapes | 0.85 | ✅ on the old wheel — all 4 |
| P2 | BLAS backend switch moves fp16 >1.5× | 0.60 | ❌ rocBLAS ≡ hipBLASLt, to within noise |
| P3 | fp16 within 20% of bf16 in some config | 0.50 | ❌ on the old wheel (best 1.68×) |
| P4 | FP8 numerically correct | 0.75 | ❌ **exactly 4× off** |
| P5 | fp32 below 25% of vector spec | 0.70 | ✅ on the old wheel — 5.2% |
| P6 | even bf16 below reachable matrix peak | 0.65 | ✅ on the old wheel — 63% |
| P7 | `e4m3fn` available on the rocm7.2 wheel | 0.80 | ✅ |
| P8 | `e4m3fn` numerically exact there | 0.70 | ✅ **bit-exact, err = 0.0** |
| P9 | `fnuz` still 4× **or rejected** | 0.65 | ✅ rejected — `HIPBLAS_STATUS_NOT_SUPPORTED` |
| P10 | fp16 gap **persists** on the newer wheel | 0.55 | ❌ **gone** — ratios 0.96–1.09 |

**P10 was the important miss**, and it was logged at 0.55 precisely because a year of
gfx1201 tuning was the obvious way for it to break. It broke that way. P4 at 0.75 was
the other costly one — I assumed a fast path was a correct path.

## What is actually worth carrying forward

1. **A stale ROCm wheel silently returns 4×-wrong FP8.** Not slow — *wrong*, with no
   error. This matters because that wheel is what ComfyUI-on-RDNA4 guides and the
   official docker images were pinning; anyone still on it is affected and cannot tell.
2. **Upgrading the wheel is worth 7.4× on fp16 and 2× on FP8 on identical silicon.**
   No code change, no kernel work. For anyone benchmarking RDNA4, the wheel is a
   larger variable than anything they are likely to be measuring.
3. **"Fast" and "correct" are independent axes.** The old FP8 path was the fastest
   thing on the card and returned garbage. Throughput without a correctness control
   is not a measurement.
4. **Version-bind every negative result before reporting it.** This receipt came
   within one step of being an upstream bug report about behaviour that was already
   fixed.

## Method notes

- **G1 clock discipline.** First pass sampled clocks at arm boundaries and caught
  idle downclocks (54% / 32% apparent spread); superseded. The pinned re-run sampled
  in a background thread *during* each timed region: 0% spread at 1024/2048/4096,
  73% at 8192 — so old-wheel 8192 figures were flagged indicative, not measured.
  Perf level restored to `auto` afterwards.
- **G2 correctness before throughput.** This is what caught the 4×. It is the only
  reason this receipt is not a false report.
- **G3 allocation outside the timed region.** The exploratory run that started all of
  this had `torch.randn` inside the loop and was mostly RNG; discarded.

## Limits

- **One card, two wheels.** No second AMD GPU, no intermediate wheel versions, so the
  exact release that fixed either issue is not identified.
- The GPU was also driving the desktop; not an idle bench.
- New-wheel numbers were taken on `auto` clocks, not pinned — they are not directly
  comparable to the pinned old-wheel run at the precision of a few percent. The
  effects here are 2–7×, far above that, so the conclusion is unaffected.
- fp32 at 8192 on the new wheel reads **1.3 TFLOP/s** against 15.6 at 4096. Anomalous,
  unexplained, not chased.
- No `hipblaslt-bench` / `rocblas-bench` comparison, which would separate "torch picks
  a bad kernel" from "the library lacks a good one."

## Files

`PREREG_GEMM_DTYPE.md`, `gemm_sweep.py`, `gemm_sweep_pinned.py`, `verify.py`
(the newer-wheel re-test), `raw_default.json`, `raw_hipblaslt.json`, `raw_pinned.json`.
