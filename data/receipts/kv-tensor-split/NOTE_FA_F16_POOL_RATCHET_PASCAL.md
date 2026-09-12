# Source analysis — does the FA f16 KV-temp pool ratchet (turboquant #325) affect Pascal?

**2026-09-11.** Prompted by [sybrand-str's comment on TheTom/llama-cpp-turboquant#325][c], which
reports a VRAM floor that ratchets a few hundred MiB per large prefill on 2× RTX 5060 Ti, traces it
to `ggml_cuda_pool_alloc<half>` in `launch_fattn`, and verifies a fix
([shizhx@9d314a5][fix]) that moves the temporaries into the compute buffer.

[c]: https://github.com/TheTom/llama-cpp-turboquant/issues/325#issuecomment-5640762148
[fix]: https://github.com/shizhx/llama-cpp-turboquant/commit/9d314a5ba4119c00dfa2321df0bd4a4873d0da02

**This is a source reading, not a measurement.** No Pascal run has been made yet; the hardware test
is pre-registered separately. Everything below is checkable from the trees named.

## Answer: yes, and Pascal is the worst case — but only with a quantized KV cache

Three facts compose.

**1. Pascal cannot avoid the TILE kernel during prefill.**
In `ggml_cuda_get_best_fattn_kernel` (`ggml/src/ggml-cuda/fattn.cu`), a cc 600 device fails every
tensor-core predicate:
- `volta_mma_available(cc)` and `ggml_cuda_should_use_wmma_fattn(cc)` both require
  `ggml_cuda_highest_compiled_arch(cc) == GGML_CUDA_CC_VOLTA`;
- `turing_mma_available`, `amd_mfma_available`, `amd_wmma_available` are all false.

It reaches the generic tail, which returns `BEST_FATTN_KERNEL_VEC` only for `Q->ne[1] <= 2` with a
quantized cache (or `Q->ne[1] == 1` unquantized, when `gqa_opt_applies` is false). **Every wider
batch — that is, every prefill — returns `BEST_FATTN_KERNEL_TILE`.** On Turing and newer, quantized
shapes have MMA and extra VEC routes; Pascal has one road.

**2. TILE always demands f16 K and V.** In both trees, the kernel→conversion switch groups TILE with
the tensor-core kernels:

```
case BEST_FATTN_KERNEL_TILE:
case BEST_FATTN_KERNEL_MMA_F16:     need_f16_K = true;  need_f16_V = true;   break;
case BEST_FATTN_KERNEL_VEC:         need_f16_K = K->type == GGML_TYPE_F32;   // quantized: no convert
```

So on Pascal, a **quantized** K/V cache is converted to f16 on every prefill. An **f16** cache is
not converted at all (`K->type != GGML_TYPE_F16` is false), so f16-KV configs cannot ratchet.

**3. On CUDA the temporary is pooled unconditionally.** `fattn-common.cuh` (live default branch
`feature/turboquant-kv-cache`, lines 1395–1444):

```
#ifdef GGML_USE_HIP
    ...  hip_f16_alloc K_f16(main_stream, pool, fa_f16_use_pool);   // raw cudaMalloc unless capturing
#else
    ggml_cuda_pool_alloc<half>   K_f16(pool);                       // always the pool
    ggml_cuda_pool_alloc<half>   V_f16(pool);
#endif
```

- **The `fa_f16_use_pool` escape is HIP-only.** Tom already added the bypass for RDNA3/4, citing
  ggml-org/llama.cpp#22107 — *"pooling this temp would negate the KV compression and OOM at long
  context"*. That is the same failure, already understood on the HIP side.
- **A tempting wrong inference, checked and rejected.** "Pascal never uses CUDA graphs, so
  `fa_f16_use_pool` would be false and Pascal escapes." It does not: that branch is not compiled on
  CUDA at all. Pascal takes the `#else`.

**The temporary is sized by the whole cache, not the batch.** `K_f16.alloc(ggml_nelements(K))` covers
every cached token being attended, so the high-water mark grows with **context length**. That is why
the floor ratchets as a session fills its window.

## The bytes are allocated twice on CUDA

`ggml_cuda_flash_attn_ext_get_alloc_size` is wired into the CUDA buffer type's `get_alloc_size` in
all three trees — turboquant `f6124e9` (`ggml-cuda.cu:980`), turboquant live (`:1008`), buun
(`:998`) — so the compute buffer **already reserves** the f16 bytes after each FA output tensor.
On CUDA, `launch_fattn` then ignores that reservation and pool-allocates the same bytes again.

So on a Pascal box with a quantized cache, the f16 temp is paid for twice: once reserved and unused,
once pooled and ratcheting. The reporter's fix collapses both into the reservation.

## Which of our binaries are affected

| tree / binary | f16 temp source | affected |
|---|---|---|
| turboquant live (`feature/turboquant-kv-cache`) | pool (CUDA) | **yes** |
| turboquant `f6124e9` — the sm_60 build on `.73`, `~/llama-cpp-turboquant/build` | pool (`fattn-common.cuh:1422-1423`) | **yes** |
| buun-llama-cpp (all our builds, `.73`/`.194`/desktop) | reserved compute buffer (`f16_extra.K/.V`) | **no** |

**buun's fork is already clean**, and not by accident: `f8f0a47a5` (2026-06-03, "cuda: reserve space
for quantize kv-cache at startup (#23907)") is the upstream change that introduced the reservation,
and buun's `launch_fattn` reads `f16_extra.K` / `f16_extra.V` with
`GGML_ASSERT(f16_extra.K != 0)` — there is no `pool_alloc<half>` for these temporaries anywhere in
the file. Turboquant took the scaffolding but kept the pool call on the CUDA side.

## Why this has not bitten our own Pascal work

Our sm_60 receipts run **f16 KV**, which is the one configuration that cannot trigger the
conversion. That is not foresight; it follows from `kv-tensor-split/RESULT_RDNA4.md` — stock
`q8_0`/`q4_0` with **K and V both quantized** at D=256 collapses to `/` on sm_60, so D=256 models on
Pascal were already restricted to f16 or to asymmetric KV.

The exposure is real for anyone running turboquant's own KV compression (`turbo*`) on Pascal at long
context — the case the fork exists for.

## What a Pascal measurement would add

The reporter has CUDA-side evidence on Blackwell. A P100 run would show whether the ratchet is worse
where TILE is unavoidable, and would put numbers on a card class Tom has no access to. Pre-registered
separately; `.194` is busy with the three-way until it clears.
