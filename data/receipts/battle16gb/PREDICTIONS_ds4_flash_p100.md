# Predictions — DeepSeek-V4-Flash IQ1_S load probe on 4× Tesla P100

Logged 2026-08-01 **before** the probe. `.194`, 4× P100 (sm_60), 64 GiB VRAM,
60 GiB RAM (58 available), 1063 MHz / 150 W.
Model: `unsloth/DeepSeek-V4-Flash-0731-GGUF` **UD-IQ1_S**, 3 shards, **82.5 GB**
(5.2 MB + 49.1 GB + 33.4 GB — shard 1 is metadata, verified against content-length).
Build: `TheTom/llama-cpp-turboquant` @ `8a891f4b5`, CUDA, `CMAKE_CUDA_ARCHITECTURES=60`.

**The sm_60 FAST_FP16 carve-out is already upstream in Tom's fork** (`common.cuh:261`
carries `&& __CUDA_ARCH__ != 600`) — confirmed by Mark, verified in the tree, no local
patch needed. Only `ggml-org/llama.cpp` still lacks it.

## What is actually being tested

Unsloth ship working GGUFs, so the **model architecture** path (deepseek4 graph, lightning
indexer, HC_COMB kernels) demonstrably works. That says little about **sm_60**: Unsloth test
on Ampere and newer, Pascal has no tensor cores, and today's wave64 ballot bug
(`TURBO3_241_WAVE64_FIX_CONFIRMED.md`) is precisely the shape of "correct everywhere anyone
tests, wrong on the one nobody does."

Two independent axes. Only the second is open.

## Predictions

| id | claim | conf |
|---|---|---|
| **P-D1** | the model **loads** (server reaches `/health` ok) with `--n-cpu-moe` | **0.55** |
| **P-D2** | if it loads, it emits **coherent** text (gzip ratio within 0.15 of an f16 control) | **0.45** |
| **P-D3** | decode rate lands in **1–6 t/s** | 0.60 |
| **P-D4** | any failure is a **CUDA/arch** fault, not an OOM | 0.40 |
| **P-D5** | `--n-cpu-moe` is **required** — it will not fit VRAM-only | **0.95** |

**P-D1 at 0.55.** The DSV4 port merged one day ago and this is its first exposure to sm_60.
A single unguarded `__CUDA_ARCH__` or a `__nv_bfloat16` intrinsic in `lightning-indexer.cu`
or `dsv4-hc.cu` would stop it. Against that: the build completed cleanly for arch 60,
including the full turboquant flash-attention template matrix, which is weak positive
evidence the CUDA path instantiates.

**P-D2 lower than P-D1 at 0.45**, and this is the honest part. IQ1_S is ~1.6 bpw on a 284B
MoE. Today's Puzzle ladder measured **Q2_K leaking reasoning on 21.1 % of samples** where
IQ4 leaked 0.0 % — low-bit models fail at *control*, not content. IQ1_S is far below Q2_K.
"It emitted words" is not the test; the gzip degeneracy gate against a control is.

**P-D4 at 0.40** because 82.5 GB against 64 GiB VRAM + 58 GiB RAM is ~122 GiB of aggregate
capacity, but KV cache, compute buffers and the non-offloaded layers all draw on the same
budget. OOM is a very live failure mode, and it would be a *boring* one.

## What gets captured either way

1. **The exact `--n-cpu-moe` value that works** (or the OOM boundary). Nobody has published a
   working config for an 82 GB model on 64 GB of 2016 GPUs; that is the useful artifact.
2. **gzip ratio vs an f16 control**, not an eyeball judgement.
3. **Decode t/s** and prompt-eval t/s, with clock state (1063 MHz / 150 W).
4. **The verbatim error** if it fails. A failure is directly reportable to Tom, who turned
   around today's Vulkan fix in hours.

## Limits

- **K=1, one prompt, one quant.** A load probe, not a benchmark. No pass/fail scoring.
- DDR4-2133 on dual E5-2650 v3 is ~60 GB/s; every offloaded expert read crosses it. Decode
  rate here is a property of this box, not of the model.
- IQ1_M (86.9 GB) and every larger quant do not fit at all, so this is the only rung
  available — no ladder, no precision comparison.
