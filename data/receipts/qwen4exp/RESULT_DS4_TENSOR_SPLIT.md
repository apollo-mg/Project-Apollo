# DS4 (`deepseek4`) tensor split on `c232282aa` — three distinct failures, and the actual cause

**2026-08-28**, `.194`, 4x P100 sm_60, `DeepSeek-V4-Flash-0731-UD-IQ1_S` (77 GB, 3 shards),
`GGML_CUDA_ALLREDUCE=internal`. Baseline from 2026-08-01: `-sm layer -ts 3,4,4,1 -fit off -fa on
-ncmoe 40` = 2.16 t/s.

## Progress since August, but still broken

| commit | config | result |
|---|---|---|
| `8a891f4b5` (2026-08-01) | `-sm tensor -ts 3,4,4,1 -ncmoe 40` | `GGML_ASSERT(src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_0)` — **failed to load** |
| `c232282aa` | `-sm tensor -ts 3,4,4,1 -ncmoe 40` | `ggml-backend-meta.cpp:1038 GGML_ASSERT(split_state.ne[j] % div == 0)` |
| `c232282aa` | `-sm tensor -ts 1,1,1,1 -ncmoe 40` | `ggml-backend-meta.cpp:730 GGML_ASSERT(split_states_equal(src_ss[0], src_ss[2]))` |

Real progress: it now **loads and reaches warm-up** ("warming up the model with an empty run")
before dying, where in August it aborted during allocation. Tom's DS4 patterns moved it forward.

Note the uneven `-ts 3,4,4,1` fails *earlier* (`:1038`) than the even `-ts 1,1,1,1` (`:730`) —
those are two different expressions of one requirement (see below), so **`-ts` ratios matter
independently of device count**.

## The actual cause — instrumented, not guessed

Added a diagnostic at the `handle_set_rows` assert. It names the tensor:

```
SET_ROWS split mismatch: dst=cache_k_l0 (view)
  src0 = kv-0 (view)                   axis=10   <- MIRRORED (the values being written)
  src1 = Meta(CUDA0..3)#leaf_14#0      axis=10
  src2 = cache_k_l0                    axis=0    <- split on AXIS_0 (the destination)
```

**It is the main KV cache, not the indexer.** `cache_k_l0` is matched by
`pattern_kv_cache` (`cache_(k|v)_l\d*`) -> `GGML_BACKEND_SPLIT_AXIS_0`, while the values written
into it are mirrored. SET_ROWS requires the two to agree, so it aborts.

That is arguably wrong for MLA specifically: DeepSeek-V4 has `head_count_kv = 1` and a *shared
latent* KV, so there is nothing per-head to split. The split-state already mirrors the
corresponding **weights** for exactly this reason —

```cpp
// DS4 q_a/kv are low-rank down-projections feeding per-row norms; column split would split
// the norm row, so mirror them
pattern_ds4_q_a_kv_weight -> GGML_BACKEND_SPLIT_AXIS_MIRRORED
```

— but the **cache** those projections feed is still split on axis 0. The weights and their cache
disagree.

## A hypothesis I tested and falsified

I first guessed the culprit was the **lightning-indexer** cache, since Tom's qwen4exp fix was
exactly "give the indexer KV cache distinct `cache_idx_*` names and mirror it in Meta", and
`llama-kv-cache-dsv4.cpp` builds `kv_lid` with **no `name_tag`** (so its tensors are named
`cache_k_l*` and get split). `"idx_"` is passed from exactly one place in the tree —
`llama-memory-hybrid-idx.cpp:58`, the qwen4exp path.

I tagged `kv_lid` with `"idx_"`, rebuilt, and reran. **It did not help — same `:730` assert.**
The diagnostic above then showed why: the mismatching tensor is `cache_k_l0`, the main cache.

Recording the falsification because the reasoning was plausible and someone else may try it.
`kv_lid` may still deserve the tag on its own merits; it is simply not what breaks first.

## Status

Local edits (the `kv_lid` tag and the diagnostic) were **reverted** before syncing on to
`d929da17b`. DS4 remains broken under `-sm tensor`; `-sm layer -ts 3,4,4,1 -ncmoe 40` remains the
working configuration.


---

## Progress ladder (updated 2026-08-29)

Each head moves the first failure further into the graph. All runs `-ts 1,1`, 2x P100,
`-ngl 99 -c 8192 -fit off -fa on -ncmoe 40 -np 1`.

| head | first failure | warm-up? |
|---|---|---|
| `8a891f4b5` (2026-08-01) | `src_ss[0].axis != SPLIT_AXIS_0` — failed to load | no |
| `c232282aa` | `:730` SET_ROWS split mismatch (`cache_k_l0` split vs mirrored values) | yes |
| `163517b9a` | `ggml-backend.cpp:472` OOB write, `attn_output_a` `ne[2]=0` | no (load) |
| `3042c600b` | central policy stop — `attn_output_a`, 1 unit for 2 devices | no |
| `1336de3bf` | `:535` UNKNOWN axis, **ROPE_BACK** routed to `handle_generic` | no |
| `1336de3bf` + ROPE_BACK fix (local, tested) | `:593` MUL_MAT MIRRORED x AXIS_2 | **yes** |
| `16f65b057` | `:597` MUL_MAT **MIRRORED x AXIS_0** (contraction dim), self-reported | **yes** |

Two of these were traced by us and adopted upstream: the `handle_flash_attn_ext` mirrored path
(`f1a0b0139`) and the `ROPE_BACK` -> `handle_rope` routing (`16f65b057`).

The remaining gap is the contraction-dimension case: a replicated weight times an activation split
along the contracted axis yields a partial product, which is what the existing `AXIS_0 x AXIS_0`
branch already returns `PARTIAL` for. Left to Tom — it changes the communication pattern, not just
the bookkeeping.
