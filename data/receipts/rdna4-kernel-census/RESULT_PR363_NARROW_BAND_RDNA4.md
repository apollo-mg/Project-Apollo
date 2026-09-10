# Result — RDNA4 narrow-band crossover is ~16× wider than the RDNA3 value it inherits

**Date:** 2026-09-10. **Hardware:** RX 9070 XT, gfx1201, HIP 7.2.53211-3d9ef42.
**Build:** `TheTom/llama-cpp-turboquant` PR #363 @ `db66310` ("populate the narrow bands from a
bisect instead of guesses"), built `-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DCMAKE_BUILD_TYPE=Release`.
**Raw:** `sweep_vector.log`, `sweep_gemm.log`. **Method:** jasstrong's — one binary, only the env
differs. `GGML_MMVF_NARROW_MIN=0 GGML_MMVF_NARROW_MAX=8192` forces the vector path;
`GGML_MMVF_NARROW_MAX=0` lets the GEMM take everything above the column limit.

## Knob verification (done before looking at any number)

jasstrong's own correction on this PR was that he drew a conclusion from a knob that turned out not
to be connected. Two independent checks first:

1. `libggml-hip.so` contains both `GGML_MMVF_NARROW_MIN`/`_MAX` and the mangled symbol
   `ggml_cuda_mmvf_narrow_band(int, ggml_type)`. (A `strings` check on the *test binary* finds
   nothing — the code lives in the backend .so. That near-miss is worth recording.)
2. **37 of 72 cases move by >5% between arms**, and the `n=3` row is ~0% for both types —
   which is exactly right, since at n=3 both arms take the vector path regardless of band.
   A connected knob must produce that null row; an inert one produces null everywhere.

## Result, k=10240, negative = vector kernel wins

**f16**

| m | n=3 | n=4 | n=8 |
|---|---|---|---|
| 4 | -0% | -1% | **-96%** |
| 8 | +1% | -1% | **-96%** |
| 16 | +1% | +4% | -96% |
| 32 | +1% | -1% | -93% |
| 64 | +6% | +0% | -93% |
| 128 | -6% | -0% | -91% |
| 256 | +0% | +4% | -86% |
| 512 | +1% | -1% | -72% |
| 1024 | +5% | -5% | -56% |
| 2048 | +1% | +1% | **-19%** |
| 4096 | -0% | +0% | **+8%** |
| 8192 | -0% | -0% | -4% |

**bf16**

| m | n=3 | n=4 | n=8 |
|---|---|---|---|
| 4 | -1% | **-96%** | -95% |
| 8 | +0% | -96% | -95% |
| 16 | +1% | -96% | -95% |
| 32 | +7% | -92% | -91% |
| 64 | +0% | -92% | -90% |
| 128 | -1% | -91% | -91% |
| 256 | +0% | -86% | -87% |
| 512 | +0% | -78% | -75% |
| 1024 | +1% | **-65%** | -55% |
| 2048 | +1% | **-41%** | -20% |
| 4096 | -1% | **+1%** | **+13%** |
| 8192 | +0% | -14% | +1% |

## Three findings

**1. RDNA4 does not track RDNA3. The crossover is between m=2048 and m=4096 for both types** —
against RDNA3's 128 (F16) and 256 (BF16), which RDNA4 currently inherits. That is roughly 8-16×.
At m=1024, BF16 n=4, the vector kernel wins by **65%** and the shipped band excludes it.

**2. RDNA4 has no floor.** At m=4 the vector kernel wins by 96%, where CDNA F16 *loses* at m=4 and
needed `min=8`. RDNA4 wants `min=0`.

**3. The F16 band is inactive at n≤5 on RDNA4.** The whole f16 n=4 row is ~0% because RDNA4's base
F16 threshold is already `ne11 <= 5`, so both arms take the vector path. The F16 band only bites at
n≥6 — where it is worth up to 96%.

## Recommendation, by jasstrong's own rule

Widest span that still wins at every n measured:

```
RDNA4  F16   [0, 2048]     (4096 is +8% at n=8)
RDNA4  BF16  [0, 2048]     (4096 is +1% at n=4, +13% at n=8)
```

## Caveats

One card, one k (10240), `test-backend-ops perf` on an idle GPU — not end-to-end decode. The
2048→4096 gap is unbisected; if the exact edge matters, intermediate widths (2560, 3072) would
place it, as 3072 did on CDNA.
