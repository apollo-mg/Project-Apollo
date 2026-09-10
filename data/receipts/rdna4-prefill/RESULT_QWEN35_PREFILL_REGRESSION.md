# gfx1201: `qwen35` prefill is 2.6–7.7× slower on Tom's fork. Decode and `llama` are unaffected.

**Date:** 2026-09-06 · **Card:** RX 9070 XT (gfx1201), ROCm 7.2.53211 · **Reported to:** TheTom
**Status:** RESULT — an isolation, not a diagnosis. Root cause not found; four candidates eliminated.
**Raw:** `raw/isolate.log`, `raw/forkbench.log`, `raw/opperf.log`, `raw/mmperf.log`, `raw/fb_*.json`

Found while benchmarking forks for the VBR article, not while chasing a bug.

## Result

All three trees built `-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DCMAKE_BUILD_TYPE=Release`,
all freshly relinked. Identical command everywhere, default f16 KV, **no turbo, no VBR, no MTP**:

```
llama-bench -m <model> -ngl 99 -fa 1 -p 512 -n 128 -r 5
```

| model | arch | fork | pp512 t/s | tg128 t/s |
|---|---|---|---:|---:|
| Llama-3.2-3B BF16 | `llama` (dense) | tq_head `f97400563` | 1666.22 ± 11.57 | 74.40 ± 0.47 |
| Llama-3.2-3B BF16 | `llama` (dense) | buun `3823c9eb6` | 1657.67 ± 12.00 | 73.58 ± 1.71 |
| Qwen3.5-9B UD-Q2_K_XL | `qwen35` (hybrid) | **tq_head** | **318.94 ± 2.71** | 87.35 ± 0.11 |
| Qwen3.5-9B UD-Q2_K_XL | `qwen35` (hybrid) | buun | **2450.99 ± 47.31** | 90.02 ± 0.65 |
| Qwen3.8-27B GSQ-RCO IQ3_S | `qwen35` (hybrid) | **tq_head** | **376.71 ± 4.36** | 29.35 ± 0.05 |
| Qwen3.8-27B GSQ-RCO IQ3_S | `qwen35` (hybrid) | buun | 961.10 ± 14.41 | 30.05 ± 0.12 |
| Qwen3.8-27B GSQ-RCO IQ3_S | `qwen35` (hybrid) | upstream `b10816` | 975.50 ± 16.86 | 29.93 ± 0.03 |

The 27B tq_head figure reproduces on an independent run: **386.50 ± 5.88**.

Three facts constrain the cause:

- **`llama` is a dead heat** — 1666 vs 1658, within noise. Not a general prefill regression.
- **Decode is a tie everywhere**, including on the affected models. Prefill only.
- **The 9B is hit harder in ratio (7.7×) than the 27B (2.6×)**, which reads more like a fixed
  per-layer cost than a bandwidth problem — the smaller model has less real work to hide it.

## Clock and power state at sample time

| fork | sclk | avg package power |
|---|---|---|
| tq_head | 2364 MHz | 56.0 W |
| buun | 2648 MHz | 66.0 W |

Neither arm is near a power limit, so this is not throttling. The lower clock on the slow arm
is most plausibly a *consequence* of stalling rather than a cause — an 11% clock delta cannot
produce a 7.7× throughput delta. Stated as measured; the causal direction is inference.

## Eliminated

- **MMQ config coverage.** `mmq-config-rdna4.cuh` carries 12 entries each for `IQ3_S`,
  `IQ3_XXS`, `Q6_K`, `Q4_K` — same as RDNA3, 260 CASEs total against CDNA's 154. The RDNA4
  gap documented in `rdna4-kernel-census/RESULT_TQ348_RDNA4.md` is TQ-specific and does not
  touch these types.
- **Build configuration.** All three Release, all `AMDGPU_TARGETS=gfx1201`.
  `GGML_HIP_NO_VMM` differs (tq_head ON, buun OFF) — but **upstream is also ON and is fast**,
  so VMM tracks the fast arm, not the slow one.
- **The SSM / hybrid kernels.** `test-backend-ops perf -b ROCm0`, both forks, all within noise:

| op (n_seq_tokens=512) | tq_head | buun |
|---|---:|---:|
| `GATED_DELTA_NET` (32 heads, 128 dim) | 617.98 µs | 600.25 µs |
| `SSM_CONV` (937×8192) | 63.07 µs | 62.12 µs |
| `SSM_SCAN` (d_state=128, 48 heads) | 1062.44 µs | ~1062 µs |

- **FA kernel selection.** Eliminated separately — see `RESULT_PR360_MMA_NOT_COMPILED.md`.
  There is only one reachable FA path on gfx1201, so nothing is being mis-selected.

So the hybrid kernels themselves are fine and the dispatch is not choosing wrongly. Something
else in the `qwen35` graph is eating prefill.

## Where the investigation stopped

`test-backend-ops perf -o MUL_MAT` emits **2 cases** on tq_head against **191** on buun
(0 vs 14 `iq3_*`), so a like-for-like kernel comparison is not obtainable from outside the
tree. No perf logger was found in the source. Narrowing further needs instrumentation Tom has
and we do not.

## Scope

One card, one backend, two `qwen35` models, default flags only. This deliberately avoids
every turbo/VBR path, so it says nothing about the configurations the fork is actually built
for — quite possibly this affects only the unaccelerated path.
