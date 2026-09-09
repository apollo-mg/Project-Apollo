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
