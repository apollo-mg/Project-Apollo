# RDNA4 GEMM by dtype — a fast FP8 path that is exactly 4× wrong, and an fp16 cliff

**Hardware:** RX 9070 XT (gfx1201, RDNA4), 15.9 GiB, driving the desktop.
**Stack:** `torch 2.10.0.dev20250926+rocm6.3` (HIP 6.3.42131) on a **ROCm 7.2.4** system.
`gfx1201` is in the wheel's compiled arch list — every path below is native, not a fallback.
**Date:** 2026-08-09. Prereg: `PREREG_GEMM_DTYPE.md`, written before the sweep.

## Headline

| shape | fp32 | fp16 | bf16 | fp8_e4m3fnuz | **bf16/fp16** | sclk |
|---|---|---|---|---|---|---|
| 1024 | 2.3 | 16.3 | 27.4 | 70.7 | **1.68×** | 2663 MHz, 0% spread |
| 2048 | 2.5 | 18.7 | 33.2 | 102.9 | **1.78×** | 2501 MHz, 0% spread |
| 4096 | 2.5 | 16.9 | 38.7 | 121.9 | **2.30×** | 2846 MHz, 0% spread |
| 8192 | 2.2 | 5.1 | 36.9 | 114.3 | **7.17×** | ⚠ 73% spread — see G1 |

TFLOP/s, median of 5, perf level pinned `high`. Spreads were ±0.0–0.9 except fp8
(±1.6–4.1). Memory copy bandwidth 585 GB/s ≈ **91% of the ~645 GB/s spec**, so the
memory system is healthy and none of this is a bandwidth artifact.

## Finding 1 — the FP8 path is fast and its answers are exactly 4× too large

This is the important one. `torch._scaled_mm` with `float8_e4m3fnuz`, `scale_a = scale_b = 1.0`:

```
got / dequant-reference   mean 4.000000   median 4.000000   std 7.7e-08
                          min  3.999990   max    4.000008
corr(got, reference) = 1.0
scale_a = 0.25  ->  relative error 0.000000   (exact)
```

The control that makes this a kernel claim rather than a precision claim: the same
fp8-quantized values multiplied in fp32 (`a8.float() @ b8.float()`) sit **0.037**
from the fp32 reference — that is fp8's own quantization cost, and it is fine. The
kernel's output sits **3.0** from that same dequantized reference, and the ratio is
a dead-constant 4.

Correlation 1.0 and std 1e-8 mean the matrix math is *perfect*. Only the magnitude
is wrong, by a constant, everywhere, at every shape and input scale tested.

**Likely mechanism:** `e4m3fnuz` uses exponent bias **8**; IEEE-style `e4m3` uses **7**.
Read fnuz operands with the wrong bias and every value is 2× off — two operands gives
exactly 4×. The cast itself is innocent: `[1.0, 2.0, 4.0] -> fnuz -> fp32` round-trips
exactly, so torch's conversion and the GEMM kernel disagree with each other.

**Why it matters:** nothing errors. Output is finite, correlated, plausible, and
arrives at 122 TFLOP/s. Any FP8 workload on this stack silently gets 4×-inflated
activations. This is the campaign's recurring shape — a green light on an instrument
that cannot see the failure — and it is the reason G2 exists in the prereg.

`float8_e4m3fn` (the non-fnuz variant) is unavailable here: *"Float8_e4m3fn is only
supported for ROCm 6.5 and above."*

I searched and found no existing report matching this signature. Related but distinct:
pytorch#119135 (`scale_result` ignored), pytorch#143465 (fp8 slow on MI300X),
ROCm#6019 (e4m3fn NotImplementedError on Navi 48). **Not verified against a current
wheel — this may already be fixed upstream, and that check is the obvious next step.**

## Finding 2 — fp16 never reaches the matrix path, and falls off a cliff at 8192

fp16 and bf16 should be near-identical on RDNA4. fp16 is **1.7×–2.3× slower** at
every clock-clean shape, and collapses to **5.1 TFLOP/s at 8192** — a 7.2× gap.

fp16's numerical output is correct (0.00035 relative error vs fp32, better than
bf16's 0.00283, exactly as the mantissa widths predict). So this is purely a
kernel-selection problem, not a correctness one.

**Bounding it from our own data rather than a spec sheet:** hardware FP8 should run
about 2× the fp16 matrix rate. We measured fp8 at 121.9, implying ~61 TFLOP/s is
reachable for 16-bit matrix work on this card. bf16 gets 38.7 (63% of that) and fp16
gets 16.9 (28%). So **bf16 is underperforming too** — fp16 is just much worse.

## Finding 3 — the BLAS backend is not the cause

Running the whole sweep under rocBLAS and again with `TORCH_BLAS_PREFER_HIPBLASLT=1`
(confirmed to take effect: `preferred_blas` moved `Cublas` → `Cublaslt`) produced
**identical numbers to within noise** at all four shapes and all dtypes. Whatever
picks the slow fp16 kernel sits below that switch.

`raw_default.json` / `raw_hipblaslt.json`.

## Prediction scoring

| ID | Prediction | Conf | Outcome |
|---|---|---|---|
| P1 | gap reproduces across ≥3 shapes | 0.85 | ✅ **CONFIRMED** — all 4 |
| P2 | BLAS backend switch moves fp16 >1.5× | 0.60 | ❌ **FALSIFIED** — identical |
| P3 | fp16 within 20% of bf16 in some config | 0.50 | ❌ **FALSIFIED** — best 1.68× |
| P4 | FP8 numerically correct | 0.75 | ❌ **FALSIFIED** — exactly 4× off |
| P5 | fp32 below 25% of ~48 TFLOPS vector spec | 0.70 | ✅ **CONFIRMED** — 2.5 = 5.2% |
| P6 | even bf16 is below reachable matrix peak | 0.65 | ✅ **CONFIRMED** — 63% of what fp8 implies |

3/6. The two highest-confidence calls held; **P4 at 0.75 was the most costly miss and
the most valuable result.** I expected a fast path to be a correct path, which is
precisely the assumption this campaign keeps finding to be unsafe.

## Gates

- **G1 clock discipline — PASS at 1024/2048/4096, FAIL at 8192.** First pass sampled
  clocks at arm boundaries and caught idle downclocks (54% and 32% apparent spread);
  that run is superseded. The pinned re-run samples in a background thread *during*
  each timed region: 0% spread at three shapes, **73% at 8192**. The 8192 fp16 number
  (5.1 ± 0.0 across 5 reps) has essentially zero throughput variance, which argues the
  clock samples are transient artifacts rather than real throttling — but the gate is
  the gate. **Treat the 7.17× figure as indicative and the 1.68–2.30× range as measured.**
- **G2 correctness before throughput — enforced.** It is what caught Finding 1.
- **G3 allocation outside the timed region — enforced.** The exploratory run that
  started this had `torch.randn` inside the loop and was mostly RNG; discarded.

## Limits

- **One wheel, one card.** A `rocm6.3` dev build dated 2025-09-26 on a ROCm 7.2.4
  system. Every negative result is a claim about this build on gfx1201, not about
  RDNA4 or ROCm generally.
- **Not reproduced on a second AMD GPU** — none available.
- The GPU was also driving the desktop; not an idle bench.
- fp8 throughput is reported for a kernel now known to be 4× wrong. Whether a
  *corrected* kernel runs at the same speed is untested.
- No comparison against `hipblaslt-bench` or `rocblas-bench` directly, which would
  separate "torch picks a bad kernel" from "the library has no good kernel."

## Files

`PREREG_GEMM_DTYPE.md`, `gemm_sweep.py`, `gemm_sweep_pinned.py`,
`raw_default.json`, `raw_hipblaslt.json`, `raw_pinned.json`.
