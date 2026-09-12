# Result — EXL3's int8 kernel does not amortize a multi-row batch, and GGUF's MMVQ does. That is the MTP gap

**Run 2026-09-12, 18:49–19:04, on `.73`** (attempt 2; attempt 1 is kept in `mtp/attempt1_cold/` and
superseded). Pre-registered in `PREREG_EXL3_MTP_SWEEP.md` (`f68b43e`) with Amendment 1 (`98bc996`),
scored by `tools/score_exl3_mtp.py`, committed with the prereg. Raw data in `mtp/`. EXL3 campaign test 4,
ledger O5.

## The cost curve

`pp64` throughput against micro-batch size, one model load per format, `-sm layer`:

| n_ubatch | 1 | 2 | 4 | 8 | 16 |
|---|---|---|---|---|---|
| **EXL3 4.00bpw** t/s | 7.45 | 10.87 | 14.27 | 17.45 | 22.85 |
| **A_X(m)** | 1.00 | 1.46 | **1.92** | 2.34 | 3.07 |
| **Q6_K** t/s | 8.24 | 17.23 | 24.09 | 31.56 | 33.92 |
| **A_Q(m)** | 1.00 | 2.09 | **2.92** | 3.83 | 4.12 |

**A 4-row batch costs EXL3 2.08× a single row; it costs GGUF 1.37×.** All five predictions confirmed,
with a clean control (tg8 spread 0.3% in both arms).

| id | prediction | result |
|---|---|---|
| P-M0 | control: tg8 varies < 10% across ubatch | **CONFIRMED.** 0.3% both arms |
| P-M1 | GGUF amortizes: A_Q(4) ≥ 2.5 | **CONFIRMED.** 2.92 |
| P-M2 | A_X(4) < A_Q(4) | **CONFIRMED.** 1.92 vs 2.92 |
| P-M3 | A_X(4) < 2.0 | **CONFIRMED.** 1.92 |
| P-M4 | A_X(8) < A_Q(8) | **CONFIRMED.** 2.34 vs 3.83 |

## This is the mechanism behind test 1's MTP asymmetry

Test 1 measured MTP buying EXL3 **1.24×** and GGUF **1.69×** at identical draft acceptance (0.693 vs
0.688). With `--draft-max 3`, each accepted step verifies up to 4 rows and yields ~3.08 tokens for both
formats. Feeding this test's costs into that:

- **EXL3:** 3.08 tokens ÷ 2.08 cost units → a predicted gain of ~1.48×.
- **GGUF:** 3.08 ÷ 1.37 → ~2.25×.
- **Predicted ratio 0.66 against a measured 1.24/1.69 = 0.73.**

Both predictions overshoot the measured gains, because this test measures only the matmul — drafting
(three sequential MTP-head passes per step) and sampling are excluded. But the *ratio* lands close, so
**the matmul's row-scaling explains most of the asymmetry, not all of it.** The remainder is drafting
overhead, which needs a depth curve to isolate (test 6's gate failed; a restart-per-depth run is the
follow-up).

## What this means for buun

The int8 GEMV allocates `sh_y[MAX_M][COLS]` in shared memory, which looks designed to hold up to 8
activation rows and reuse each decoded weight across them. At 4 rows it nonetheless delivers 1.92×
throughput where a bandwidth-bound MMVQ delivers 2.92×.

**On Pascal that kernel is compute-bound on trellis decoding, not bandwidth-bound** — 7 t/s over 13.4 GB
of weights is about 94 GB/s against the P100's 732 GB/s. So if the decode is repeated per row rather
than shared across the batch, each extra row costs nearly full price. **Closing that would raise EXL3's
MTP gain and take back much of the 0.646× deployment gap** measured in test 1.

**Above the 8-row limit**, where both kernels fall back — EXL3 to reconstruct + cuBLAS, GGUF to
dequantize + cuBLAS — EXL3 gains 1.31× from ub 8 to 16 while GGUF gains only 1.08×. EXL3's fallback path
is comparatively strong at larger batches, which fits the prefill parity measured in test 1.

## What attempt 1 would have said

**The opposite.** Attempt 1 read A_X(4) = 2.92 against A_Q(4) = 2.94 — EXL3 amortizing exactly as well as
GGUF, which would have falsified the hypothesis. Its baseline was the first test after a 318 s load, and
was cold: EXL3's tg8 read 5.42 t/s there against 6.95 everywhere after. **The control caught it** (28.5%
spread), the prereg made the whole run descriptive, and Amendment 1 added a trailing warm `ub 1`
measurement. With a warm baseline the same kernel reads 7.45 rather than 4.88 t/s, and A_X(4) becomes
1.92.

## Deviations and limits

- **A concurrent load overlapped this run and did not perturb it.** The 5.00bpw KLD arm attempted three
  8 GB allocations at 19:02:03–19:02:17, inside this window, and failed (see `RESULT_EXL3_KLD.md`).
  **Every non-baseline measurement matches attempt 1 to the digit** — X at ub 4: 14.27 both times, ub 8:
  17.44 / 17.45, ub 16: 22.83 / 22.85, with Q identical — so the collision left no trace. That
  reproducibility is also the best evidence the ub 1 baseline was the only thing wrong with attempt 1.
- **`-sm layer`, not tensor split.** llama-bench has no tensor mode, while test 1's asymmetry was
  measured under `-sm tensor`. The kernel question is the same, but the absolute speeds are not test 1's.
- **`A(m)` understates a perfect kernel**, because pp64 includes attention and per-launch overheads that
  do not scale with rows.
- **One node, one prompt length, three reps per point.**
