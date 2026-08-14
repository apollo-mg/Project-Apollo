# DeepSeek V4 Flash on 4x P100: the MoE cache ENGAGES and makes it 2.6-3.8x SLOWER

**Date:** 2026-08-14 · **Node:** `.194`, 4x Tesla P100-PCIE-16GB (sm_60), **150 W / 405 MHz
idle at sample time** (standing fleet config since 2026-07-17) · **Build:**
`moe-cache-cuda` @ `bb3c3fa`, CUDA 12.4
**Model:** `DeepSeek-V4-Flash-0731-UD-IQ1_S`, 76.87 GiB, 284.33 B params, `deepseek4`,
43 blocks, 256 experts / 6 used / 1 shared

## Result: the cache loses in both orderings

`llama-bench`, `-ngl 999 -fitt 1024 --repack off --n-gen-warmup 32 -r 2 -n 64`, tg64:

| ordering | `--moe-cache off` | `--moe-cache auto` | ratio |
|---|---|---|---|
| forward (off first) | 5.94 ± 0.86 | **2.28 ± 0.57** | **2.6x slower** |
| reversed (auto first) | 7.59 ± 0.17 | **1.98 ± 0.51** | **3.8x slower** |

Both orderings run because this fleet has repeatedly produced position artifacts of 2-3.9x
on identical configs. Here the direction is stable and the margin is far outside it.

## Engagement is PROVEN, so this is not a placement artifact

`fit=1` alone would not have been enough — it says the evaluator *chose* a cache placement,
not that pools allocated or a single expert was served. That distinction is what voided the
Vulkan control in `RESULT_HIP_VULKAN.md`. Verified separately with `-v` and
`GGML_CUDA_MOE_CACHE_STATS=32`:

```
[moe-cache] enabled
[moe-cache] CUDA0 pool[0]: type=iq3_xxs expert=3136 KiB slots=841  entries=1280 total=2575 MiB
[moe-cache] CUDA0 pool[1]: type=iq1_s   expert=1600 KiB slots=1308 entries=2048 total=2043 MiB
[moe-cache] CUDA0 pool[2]: type=iq2_xxs expert=2112 KiB slots=375  entries=512  total=773 MiB
[moe-cache] CUDA3 pool[0]: type=iq3_xxs expert=3136 KiB slots=1716 entries=2816 total=5255 MiB
[moe-cache] CUDA3 pool[1]: type=iq2_xxs expert=2112 KiB slots=1867 entries=3072 total=3850 MiB
[moe-cache] CUDA3 pool[2]: type=iq1_s   expert=1600 KiB slots=1867 entries=3072 total=2917 MiB

hits=8280/14514 (57.0%)   hits=8341/14514 (57.5%)   hits=7952/13398 (59.4%)
```

**The cache ran, allocated 17.4 GiB of pools across two devices, and served 57-59% of
expert lookups — and the model still ran 2.6-3.8x slower than with the cache off.**

## Why this is the opposite of the Darwin-36B result

`Finding 5` in `RESULT_HIP_VULKAN.md` measured **~2x faster** on this same node, same build,
with the cache on. The differences that matter:

| | Darwin-36B `Q6_K` | DeepSeek V4 `UD-IQ1_S` |
|---|---|---|
| size vs fleet VRAM (64 GiB) | 26.55 GiB — **fits** | 76.87 GiB — **exceeds by 20%** |
| routed expert weights | modest | **72048 MiB** |
| projected cache capacity | ample | 40036 MiB = **55.6% coverage** |
| experts / used | 256 / 8 | 256 / **6** |
| measured hit rate | 59.5% | 57-59% |
| result | **2.0-2.1x faster** | **2.6-3.8x slower** |

Hit rate is nearly identical in both. **Hit rate is therefore not the thing that determines
whether the cache pays.**

The candidate explanation, stated as a hypothesis and not measured here: fit chose
**main-device dense placement**, concentrating dense layers on CUDA0 —

```
CUDA0 leaves  4363 MiB after reserve
CUDA1 leaves 11891 MiB
CUDA2 leaves 11891 MiB
CUDA3 leaves 11891 MiB
```

— and then allocated pools on CUDA0 and CUDA3 only. With 43% of expert lookups still
missing to host memory over PCIe, and dense compute concentrated on the card with the least
free VRAM, the reorganisation cost may simply exceed what a 57% hit rate returns. At 55.6%
projected coverage there is no configuration in which the cache avoids host traffic on the
critical path.

## What this does and does not establish

**Does:** on a model that exceeds fleet VRAM by 20%, with only ~56% of routed experts
coverable, cache-aware placement is **actively harmful** on this hardware — 2.6-3.8x, both
orderings, engagement proven. This is the first measured case in this fleet where the cache
is worse than stock.

**Does not:** identify the mechanism. Placement concentration, PCIe miss traffic, and pool
distribution are all confounded in a single `auto` decision. Separating them needs runs that
pin placement while varying cache state, which `-fitt` by design does not allow.

**Does not** generalise to models that fit VRAM, where the Darwin result stands unchanged.

## Practical reading

Coverage, not hit rate, looks like the variable to watch. Both models hit ~57-59%, and one
gained 2x while the other lost 3x. The distinguishing number is **projected coverage of
routed expert weights**: ample for Darwin, 55.6% here. Anyone running `--moe-cache auto` on
a model substantially larger than their VRAM should measure both arms before trusting it,
and the fit log prints the coverage figure needed to predict the risk.

## Limits

- `-r 2`, single node, one quant, one context length. K is small.
- The `off` arm differed **5.94 vs 7.59 t/s** between orderings — a 28% spread on an
  identical configuration. Position variance is real even in the control arm; the cache
  deficit is much larger than that spread, but the absolute numbers are soft.
- Engagement was verified in a **separate run** from the timed arms, not the same one.
- No quality measurement. This is throughput only.
- `deepseek4` reports `?B` for its size class in `llama-bench`; params read 284.33 B.
