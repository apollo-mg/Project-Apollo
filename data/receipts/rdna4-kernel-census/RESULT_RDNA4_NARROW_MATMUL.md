# Result — RDNA4 (gfx1201) narrow-matmul census

**Date:** 2026-09-09. **Hardware:** RX 9070 XT, gfx1201 (0x1201), Wave Size 32, 16304 MiB.
**Build:** buun-llama-cpp, local test cases added to `tests/test-backend-ops.cpp`.
**GPU idle at start** (mclk 96 MHz, sclk 0 MHz, 13.0 W) — no other GPU work running.
**Raw:** `raw_rdna4_narrow_matmul.log`. **Pre-registered:** `PREREG_NARROW_MATMUL_RDNA4.md`.
Context: jasstrong's narrow-matmul work on `TheTom/llama-cpp-turboquant` #362 / #363.
gfx1201 was absent from his gfx90a / gfx1100 / gfx1030 table.

## Headline

**On RDNA4 the `mmvf` path is the SLOW path for `m=10240, k=320`, and F16's explicitly-tuned
threshold of `ne11 <= 5` keeps it there two rungs longer than BF16 — costing 3.2-3.6×.**

`should_use_mmvf()` gives RDNA4 `f16 <= 5` (tuned) and `bf16 <= 3` (flat default). That
disagreement makes BF16 a **built-in control**: the two dtypes move the same bytes and differ
only in which kernel they select.

| n | f16 µs | bf16 µs | f16/bf16 | mmvf? |
|---|---|---|---|---|
| 1 | 23.04 | 22.89 | 1.01× | both in |
| 2 | 30.43 | 29.84 | 1.02× | both in |
| 3 | 36.29 | 38.21 | 0.95× | both in |
| 4 | 44.50 | **13.96** | **3.19×** | f16 in, bf16 **out** |
| 5 | 51.10 | **14.18** | **3.60×** | f16 in, bf16 **out** |
| 6 | 14.80 | 14.48 | 1.02× | both out |

Within 5% at every n where the paths agree; 3.19× and 3.60× apart at exactly the two n where
they differ; converged again at n=6. The kernel choice is the only variable.

Effective bandwidth (6.55 MB weight / time, 640 GB/s theoretical):

| n | f16 | bf16 |
|---|---|---|
| 4 | 147 GB/s (23.0%) | **470 GB/s (73.4%)** |
| 5 | 128 GB/s (20.0%) | **462 GB/s (72.2%)** |

Inside mmvf, F16 *loses* throughput as n grows (180→147→128 GB/s for n=3,4,5). The GEMM path
holds ~70% of theoretical. **Lowering the RDNA4 F16 threshold from 5 to 3 should recover ~3.2×
at n=4 and ~3.6× at n=5 for this shape class.**

## Full table (all 22 cases)

| dtype | m | n | k | µs/run | GFLOPS |
|---|---|---|---|---|---|
| q8_0 | 4 | 1 | 10240 | 7.89 | 10.4 |
| q8_0 | 4 | 4 | 10240 | 18.42 | 17.8 |
| q8_0 | 320 | 1 | 10240 | 10.36 | 632.3 |
| q8_0 | 320 | 4 | 10240 | 16.21 | 1620 |
| q8_0 | 10240 | 1 | 320 | 32.38 | 202.4 |
| q8_0 | 10240 | 4 | 320 | 13.55 | 1940 |
| f16 | 4 | 1 | 10240 | 6.14 | 13.3 |
| f16 | 4 | 4 | 10240 | 7.45 | 44.0 |
| f16 | 320 | 1 | 10240 | 10.27 | 638.4 |
| f16 | 320 | 4 | 10240 | 14.15 | 1850 |
| f16 | 10240 | 1..6 | 320 | 23.04 / 30.43 / 36.29 / 44.50 / 51.10 / 14.80 | 284→641, then 2660 |
| bf16 | 10240 | 1..6 | 320 | 22.89 / 29.84 / 38.21 / 13.96 / 14.18 / 14.48 | 286→515, then 1880→2720 |

## Prediction scoring

**P1 — no segfault on gfx1201. Logged 80%. CONFIRMED.**
`MUL_MAT type_a=q8_0, m=10240, n=4, k=320` passes correctness cleanly; exit 0, no fault, and no
`amdgpu` ring reset or fault in dmesg. The trio and the bf16/f16 sweep also pass. jasstrong's
crash appears RDNA2-specific: clean on gfx1100 (RDNA3), gfx90a (CDNA) and now gfx1201 (RDNA4).

**P2 — BF16 breaks at n=3→4, F16 not until n=5→6. Logged 70%. CONFIRMED, exactly.**
Predicted from the source thresholds before measuring; both discontinuities land where predicted.

**P3 — BF16 *penalty* at n=4 vs n=3 > 1.3×. Logged 50%. FALSIFIED ON SIGN.**
Observed 38.21 → 13.96 µs: a **2.74× speedup**, not a penalty. The magnitude bar was cleared but
the direction was inverted. **I assumed mmvf was the fast path and leaving it was the cost.** The
opposite is true at this shape. I flagged in the prereg that I had "no prior on the fallback path's
cost," which is precisely the gap that produced the wrong sign — the caveat identified the weakness
but did not stop me from asserting a direction.

This also inverts the prereg's framing: BF16's *untuned* flat `<= 3` is the better setting here, and
F16's *tuned* `<= 5` is the pessimization.

**P4 — `m=4, k=10240` is the worst shape by bandwidth fraction. Logged 75%. CONFIRMED.**
f16 13.3 GB/s (**2.1%** of theoretical), q8_0 10.4 GB/s (1.6%) — an order of magnitude below
every other shape. A 10240-deep reduction producing 4 outputs.

## Caveats

- `m=320, k=10240` reads 638 GB/s ≈ 99.7% of theoretical. That is **not** VRAM bandwidth —
  the 6.55 MB weight is resident in the 64 MB Infinity Cache. Do not quote it as a DRAM figure.
  The same 6.55 MB as `m=10240, k=320` takes 10.27 µs vs 23.04 µs, so layout costs 2.2× at
  identical byte count.
- Perf mode, single GPU, no other load. Not a model-level end-to-end claim.
- **Guard false-positive:** the run's own guard warned "perf result lines: 2" of an expected 26.
  That was a bad counting grep — `test-backend-ops` prints the `runs - µs/run - GFLOPS` figures on
  a *separate line* from the `MUL_MAT(...)` header whenever the CUDA-graph warmup message
  interleaves, so only the 2 non-interleaved cases matched. 28 timing lines and 22 unique cases are
  present. The guard failed safe (cried wolf rather than passing bad data), but the counter must be
  `grep -c 'us/run'`.

## Not yet sent anywhere

Nothing here has gone to Tom or jasstrong. Any outreach needs Mark's explicit approval and his own words.

---

# Addendum — inside jasstrong's narrow window (#363). The earlier headline was outside it.

**Date:** 2026-09-09, same session. **Raw:** `raw_rdna4_narrow_window.log` (36 timing lines).

## Why this addendum exists

#363 gates its change on `src0_ne[1] <= GGML_MMVF_NARROW_MAX` (default **4096**), and
`src0_ne[1]` is **m**. The headline table above is at **m=10240**, which is *outside* that window —
so it does **not** speak to his patch. Framing it as though it did would have been wrong.
These are the measurements inside the window.

Also relevant: `fp32_mma_hardware_available()` is `GGML_CUDA_CC_IS_CDNA(cc)` — his F32 arm cannot
reach RDNA4. But `bf16_mma_hardware_available()` is `... || cc >= GGML_CUDA_CC_RDNA3`, which
**does** include RDNA4. **His BF16 arm changes RDNA4 behaviour.**

## Result — the patch's premise holds on RDNA4, harder than on MI210

f16 (`ne11 <= 5`) vs bf16 (`ne11 <= 3`) again used as a natural A/B: the cliffs land exactly at
those constants, which confirms the thresholds empirically.

**m=320, k=10240:**

| n | f16 µs | bf16 µs | paths |
|---|---|---|---|
| 1-3 | 10.18 / 11.74 / 12.74 | 10.04 / 11.75 / 15.64 | both mmvf |
| **4** | **13.84** | **118.10** | f16 mmvf, bf16 **GEMM — 8.5× worse** |
| **5** | **15.43** | **121.49** | f16 mmvf, bf16 GEMM |
| 6-8 | 121.93 / 124.88 / 127.73 | 123.97 / 127.46 / 130.40 | both GEMM |

**m=4, k=10240:**

| n | f16 µs | bf16 µs | paths |
|---|---|---|---|
| 1-3 | 6.06 / 6.34 / 6.84 | 5.99 / 6.38 / 10.18 | both mmvf |
| **4** | **7.46** | **244.18** | f16 mmvf, bf16 **GEMM — 32.7× worse** |
| **5** | **7.45** | **244.72** | f16 mmvf, bf16 GEMM |
| 6-8 | 204.52 / 204.76 / 204.96 | 242.64 / 242.71 / 243.22 | both GEMM |

## Three conclusions

1. **The patch's premise is confirmed on RDNA4, and the effect is far larger than his MI210
   numbers (29% at four rows).** Inside the window the GEMM costs **8.5×** at m=320 and **32.7×**
   at m=4 at n=4. A GEMM producing 4 output columns really is almost all setup.

2. **`GGML_MMVF_NARROW_MAX = 4096` is well placed for RDNA4.** Both sides now measured on the
   same hardware: inside the window mmvf wins by 8.5-32.7×; outside it (m=10240, headline table)
   the GEMM wins by 3.2-3.6×. The gate is doing real work, and 4096 separates our two data points
   correctly. We have not bisected where the true crossover lies between 320 and 10240.

3. **The same cliff remains in F16 after the patch, and on RDNA4 it is expensive.** #363 modifies
   only the F32 and BF16 branches. The F16 AMD branch has its own `GGML_CUDA_CC_IS_RDNA4(cc) →
   ne11 <= 5` and **no narrow-weight case**, so F16 still falls off at n=6:
   **7.45 → 204.52 µs at m=4 (27.5×)** and **15.43 → 121.93 µs at m=320 (7.9×)**.
   Extending the same `src0_ne[1] <= narrow_max` guard to the F16 branch looks worth it on RDNA4.

## Caveat

Perf-mode microbenchmarks on an idle GPU, not end-to-end decode. We have no qwen4exp model that
fits 16 GB, so we cannot reproduce his ms/token table — only the kernel-level crossover.
