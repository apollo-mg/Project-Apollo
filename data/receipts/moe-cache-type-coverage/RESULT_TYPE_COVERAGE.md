# Why Vulkan can't reproduce the CUDA MoE-cache win: the expert tensors are MXFP4

Answering Defilan's ask — *"if you can gguf-dump which ggml types UD-Q8_K_XL puts
on the expert tensors, I'll target that kernel."* Done without downloading the
model: the GGUF tensor table sits at the head of each shard, so HTTP range
requests over all five shards are enough (`gguf_remote_dump.py`).

## The model

`unsloth/DeepSeek-V4-Flash-0731-GGUF` → `UD-Q8_K_XL`, all 5 shards, 1328 tensors.

```
arch deepseek4, block_count 43, expert_count 256, expert_used_count 6

EXPERT tensors:      MXFP4 x 129        (ffn_gate_exps 43, ffn_up_exps 43, ffn_down_exps 43)
NON-EXPERT tensors:  BF16 x 555, F32 x 641, I32 x 3
```

**Every expert tensor is MXFP4. Not one tensor in the file is Q8_0** — despite
the name `UD-Q8_K_XL`. The experts are 4-bit microscaling; the "Q8_K_XL" refers
to the non-expert treatment, which here is BF16.

This is the sharpest instance yet of a label not being a spec (see
`gguf-label-is-not-a-spec`): a model advertised as Q8 whose experts are 4-bit.

## Why that settles the Vulkan/CUDA disagreement

Backend type coverage, read straight from the sources:

| backend | types the MoE cache implements |
|---|---|
| **Vulkan** (`ggml-vulkan-moe-cache.cpp`) | **Q4_0, Q4_K, Q6_K, Q8_0** — four |
| **CUDA** (`moe-cache.cu`) | Q4_0/Q4_K/Q6_K/Q8_0 **plus MXFP4, NVFP4, Q1_0, IQ1_S, IQ1_M, IQ2_XXS, IQ2_XS, IQ2_S, IQ3_XXS, IQ3_S, IQ4_NL, IQ4_XS** |

`GGML_TYPE_MXFP4 = 39` (`ggml.h:429`), confirmed.

So:

1. **Jabba's 10→15 t/s is real** — CUDA implements an MXFP4 expert-cache kernel.
2. **Defilan cannot reproduce it on Vulkan with that model, ever.** There is no
   MXFP4 path in the Vulkan cache. Not a broken setup, not a UMA artifact — the
   kernel does not exist.
3. His answer to "which kernel should I target" is **MXFP4**.

His own Q6_K null stands separately and is still valid: Q6_K *is* supported on
Vulkan, so that run exercised a real kernel and legitimately found no effect —
which UMA explains, since caching CPU-resident experts in "spare VRAM" moves
RAM→same RAM when there is no PCIe hop to avoid.

## The broader scope limit nobody has stated

Vulkan and Metal cache v1 cover **four** types. CUDA covers **sixteen**. Most
widely-distributed MoE quants — anything IQ-flavoured, anything MXFP4-native
(gpt-oss class), anything unsloth-dynamic — will silently no-op on Vulkan and
Metal while working on CUDA. Any cross-backend benchmark that doesn't first
check the expert tensor types is comparing a live kernel against a no-op.

## Method

`gguf_remote_dump.py <shard-urls...>` — parses GGUF header + tensor table via
`Range:` requests, ~4 MiB per shard instead of the full download. Reusable for
any HF-hosted GGUF, and cheap enough to run before committing to a benchmark.
