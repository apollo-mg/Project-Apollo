# gfx1201: the MMA flash-attention path has no device code, so PR #360's A/B has nothing to switch between

**Date:** 2026-09-06 · **Card:** RX 9070 XT (gfx1201), ROCm 7.2.53211 · **Build:** `cc1a79194`
`-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DGGML_HIP_NO_VMM=ON -DCMAKE_BUILD_TYPE=Release`
**Posted to:** TheTom/llama-cpp-turboquant PR #360 · **Raw:** `raw/fa_ab.log`, `raw/fa_ab.sh`

PR #360 adds `GGML_HIP_FA_KERNEL` to override flash-attention kernel selection. This tests
whether the `qwen35` prefill regression (`RESULT_QWEN35_PREFILL_REGRESSION.md`) is a
kernel-selection problem the override can fix.

## Result — it is not, because there is only one reachable kernel

### Qwen3.5-9B UD-Q2_K_XL

| case | pp512 avg | five samples |
|---|---:|---|
| `env -u GGML_HIP_FA_KERNEL` | **314.27 ± 3.86** | 313.62, 315.27, 307.92, 317.46, 317.06 |
| `GGML_HIP_FA_KERNEL=tile` | **315.81 ± 0.93** | 316.59, 316.65, 314.70, 316.19, 314.91 |
| `GGML_HIP_FA_KERNEL=mma` | **run fails** | — |

tg128: default 87.24 ± 0.15, tile 87.35 ± 0.18.

### Qwen3.8-27B GSQ-RCO IQ3_XXS

| case | pp512 avg | five samples |
|---|---:|---|
| `env -u GGML_HIP_FA_KERNEL` | **366.18 ± 1.62** | 366.03, 368.36, 363.85, 365.98, 366.67 |
| `GGML_HIP_FA_KERNEL=tile` | **378.06 ± 2.30** | 374.45, 377.25, 379.47, 380.30, 378.82 |
| `GGML_HIP_FA_KERNEL=mma` | **run fails** | — |

tg128: default 29.20 ± 0.06, tile 29.24 ± 0.07.

## Why `mma` produces no result

```
fattn-mma-f16.cuh:2121: ERROR: HIP kernel flash_attn_ext_f16 has no device code
compatible with HIP arch 1300.
```

Repeated for every launch, no output rows. The MMA flash-attention kernel has **no gfx1201
device code in this build**, so `BEST_FATTN_KERNEL_MMA_F16` is not a reachable target on
RDNA4 — the override returns it, the launch finds nothing compiled, and the run dies.

## Reading

**`default` and `tile` are the same path.** 314.27 vs 315.81 on the 9B; 366.18 vs 378.06 on
the 27B. The second is ~3% and nothing should be read into it. Default dispatch was already
choosing TILE, because on this arch there is nothing else to choose.

So the regression is **not** a kernel-selection fault. On gfx1201 the fork has exactly one
usable FA prefill path and it is the slow one. The open question stays the one from the
companion receipt: why TILE here is 2.6× (27B) to 7.7× (9B) slower than upstream/buun on the
same card and model — not which of two paths gets picked.

The A/B PR #360 designed becomes answerable only with a build that compiles the MMA instances
for gfx1201. Offered to Tom; unanswered as of 2026-09-07.

## Scope

One card, one backend, default flags, no turbo/VBR. Both models are `qwen35`; no `llama`-arch
control was run under the override, because the companion receipt already shows `llama` is
unaffected on this card.
