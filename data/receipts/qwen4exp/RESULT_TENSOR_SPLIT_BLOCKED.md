# `qwen4exp` cannot use tensor parallelism — because it is missing from a switch, not because the math is missing

**2026-08-28**, `.194`: 4x Tesla P100-PCIE-16GB (sm_60), `TheTom/llama-cpp-turboquant` PR #324
@ `d74823a0c`, `Qwen3.8-Flash-Next-UD-Q2_K_XL`, all 48 layers GPU-resident, 150W/1063MHz.

> **Correction, same day.** The first version of this receipt said the block was "dimension
> arithmetic in `llama_meta_device_get_split_state`" and framed it as the split-state calculator
> being unable to describe hybrid linear/full attention. **That was wrong in the way that
> matters.** The calculator already contains exactly the right arithmetic — a dedicated branch
> for the Qwen gated-delta-net family. `qwen4exp` simply is not in the `if` that reaches it, and
> a permissive default let it past the gate that should have rejected it. Design problem vs.
> two-line omission. The corrected account is below.

## The block

`-sm tensor` aborts during tensor allocation, before any token is produced:

```
llama-model.cpp:583: GGML_ASSERT(tensor->ne[axis] == n_embd + 2*n_embd_gqa) failed

llama_meta_device_get_split_state(...)::{lambda(int, unsigned int)#1}   <- get_split_segments
  -> llama_meta_device_get_split_state(...)
  -> ggml_backend_meta_get_split_state(...)
  -> ggml_backend_meta_buffer_init_tensor_impl(...)
  -> ggml_backend_meta_alloc_ctx_tensors_from_buft
```

## Root cause: a deny-list default plus an incomplete switch

Two independent things had to be true, and both were:

**1. The gate is a deny-list.** `llm_arch_supports_sm_tensor()` (`llama-arch.cpp:1099`) lists 26
architectures that return `false`, then `default: return true`. Every new architecture is opted
into tensor-split **by omission**. `qwen4exp` was never added, so `llama_model_create` let it
through.

**2. The calculator's Qwen branch does not list it.** Inside
`llama_meta_device_get_split_state`, `get_split_segments` opens with:

```cpp
if (arch == LLM_ARCH_QWEN3NEXT || arch == LLM_ARCH_QWEN35 || arch == LLM_ARCH_QWEN35MOE) {
    const int64_t key_dim   = hparams.ssm_d_state * hparams.ssm_n_group;   // 128 * 16 = 2048
    const int64_t value_dim = hparams.ssm_d_state * hparams.ssm_dt_rank;   // 128 * 48 = 6144
    ...
    GGML_ASSERT(tensor->ne[axis] == 2*key_dim + value_dim);                // 10240
```

`qwen4exp` is absent, so it falls through to the generic dense-attention path, which asserts
`n_embd + 2*n_embd_gqa` = `2560 + 2*512` = **3584**. The real tensor is
`blk.0.attn_qkv.weight` = `[2560, 10240]`. Abort.

**10240 is exactly what the Qwen branch expects.** The branch it never reached would have passed.

## Every formula in that branch is already correct for this model

Checked against the actual GGUF header, not inferred:

| tensor | actual shape | Qwen-branch formula | value |
|---|---|---|---|
| `attn_qkv.weight` | `[2560, 10240]` | `2*key_dim + value_dim` | 10240 ✅ |
| `attn_gate.weight` | `[2560, 6144]` | `{key_dim, head_ratio}` = 2048x3 | 6144 ✅ |
| `ssm_out.weight` | `[6144, 2560]` | `{key_dim, head_ratio}` | 6144 ✅ |
| `ssm_conv1d.weight` | `[4, 10240]` | `{key_dim, 2+head_ratio}` = 2048x5 | 10240 ✅ |
| `ssm_alpha/beta.weight` | `[2560, 48]` | `{n_k_heads, head_ratio}` = 16x3 | 48 ✅ |
| `ssm_dt.bias`, `ssm_a` | `[48]` | `{n_k_heads, head_ratio}` | 48 ✅ |

hparams from the GGUF: `ssm.state_size` 128, `ssm.group_count` 16, `ssm.time_step_rank` 48,
`ssm.inner_size` 6144, `embedding_length` 2560, `head_count` 24, `head_count_kv` 2,
`key_length`/`value_length` 256, `full_attention_interval` 4, `block_count` 48.

The hparam mapping is not a guess either — `src/models/qwen4exp.cpp:113-116` uses
`ssm_d_state` / `ssm_n_group` / `ssm_dt_rank` for head-k-dim / n-k-heads / n-v-heads in
**byte-identical** lines to `llama-model.cpp:534-537`.

## Which broadcast pattern — settled by two independent lines of evidence

The Qwen branch splits in two: Qwen3Next uses **interleaved** K→V broadcast
(`[k0v0, k0v1, k1v2, k1v3]`), Qwen 3.5 uses **tiled** (`[k0v0, k1v1, k0v2, k1v3]`).
`qwen4exp` is tiled:

1. **The explicit repeat is character-identical to Qwen 3.5's.** `qwen4exp.cpp:780-781` and
   `qwen35.cpp:446-447` both call `ggml_repeat_4d(q_conv, head_k_dim, num_v_heads, ...)`
   directly — plain tiling. `qwen3next.cpp:527-536` instead does a reshape→repeat→reshape to
   build a repeat-interleave.

2. **The fused-GDN guard is identical to Qwen 3.5's and differs from Qwen3Next's.**
   `qwen4exp.cpp:778` and `qwen35.cpp:444` both skip the repeat entirely when
   `fused_gdn_ar && fused_gdn_ch` — they rely on the fused op's built-in broadcast.
   `qwen3next.cpp:521` has **no** such escape; it always materialises the repeat, and carries
   the TODO `[TAG_GGML_GDN_BCAST]` "avoid repeats for fused GDN, needs broadcast configuration".
   `ggml.h:2575` confirms the op has a single hard-coded broadcast mode. So the fused op is
   tiled, and the two archs that trust it are the tiled ones.

## The patch

Two lines. Add `LLM_ARCH_QWEN4EXP` to the arch condition at `llama-model.cpp:533`
(`get_split_segments`) and `:646` (`get_split_granularity`, the doubled-Q-gate granularity).
Deliberately **not** to the inner `if (arch == LLM_ARCH_QWEN3NEXT)` at `:544` — that is what
keeps it on the tiled branch.

Result of that patch: see `RESULT_TENSOR_SPLIT_PATCHED.md`. Predictions logged before the run
in `PREDICTIONS_tensor_split_patch.md`.

**This is not a missing kernel.** Single-GPU numerics are exact (NMSE 3.04e-14 vs CPU) and the
PR touches zero `ggml-cuda` files.

## Why it matters

Every Flash-Next throughput number in `RESULT_FLASHNEXT_PASCAL.md` was measured on `-sm layer`,
which is **pipelined**: with `-np 1` each token walks all 48 layers in order, so the cards take
turns. Measured during decode: `nvidia-smi` = `0% / 0% / 90% / 0%`. That is what layer-split
does with a single sequence, not a symptom of anything.

| | |
|---|---|
| active expert weights/token | **858 MiB** (10 of 512 experts x 48 layers @ Q2_K_XL) |
| one P100 @ ~500 GB/s effective | 1.7 ms -> **~597 tok/s** bandwidth ceiling |
| measured | **15-16 tok/s** |

## What caps the upside on THIS box

`nvidia-smi topo -m`:

```
GPU0 <-> GPU1   PHB   (same root complex, NUMA 0)
GPU2 <-> GPU3   PHB   (same root complex, NUMA 1)
GPU0/1 <-> GPU2/3   SYS   <- across the inter-socket link
```

Two NUMA domains, two GPUs each, no NVLink. Tensor parallelism all-reduces **per layer**, so
4-way crosses the socket boundary 48 times per token. That is also why
`GGML_CUDA_ALLREDUCE=internal` is mandatory here — NCCL fails on that same `SYS` hop
(`ggml_backend_cuda_comm_allreduce_nccl`, `ggml-cuda.cu:1105`), reproduced again today when the
arch test was run without it.

2-way tensor split inside one NUMA domain would communicate cleanly, but 32 GiB cannot hold the
~44 GiB resident at Q2_K_XL. **Estimate, not measurement**, and see the predictions file for why
I now hold it loosely.
