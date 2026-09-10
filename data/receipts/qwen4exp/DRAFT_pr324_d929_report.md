# DRAFT — PR #324 reply for `d929da17b`. For Mark to review. NOT POSTED.

---

Synced to `d929da17b` on the 4x P100 box. Short version: **the fix is right, but it needs one
more change to land** — mirroring dense attention immediately breaks flash attention, which
tensor split force-enables. With that added, both real-model checks pass.

## `d929da17b` alone aborts

```
ggml-backend-meta.cpp:748 GGML_ASSERT(src_ss[0].axis == GGML_BACKEND_SPLIT_AXIS_2) failed
```

`handle_flash_attn_ext` requires Q/K/V split on axis 2; your fix now hands it MIRRORED tensors
and there's no mirrored path. This is on the critical path for **every** tensor-split run, since
llama.cpp force-enables FA:

```
llama_init_from_model: enabling flash_attn since it is required for SPLIT_MODE_TENSOR
```

`handle_gated_delta_net`, 12 lines below, already has the early-out this needs:

```cpp
 auto handle_flash_attn_ext = [&](const std::vector<ggml_backend_meta_split_state> & src_ss) -> ggml_backend_meta_split_state {
+    // Undersubscribed GQA (n_head_kv < n_devices) mirrors the whole attention subgraph, so
+    // Q/K/V arrive MIRRORED rather than split by head. Mirror the output too. Same shape as
+    // the all-mirrored early-out in handle_gated_delta_net below.
+    if (src_ss[0].axis == GGML_BACKEND_SPLIT_AXIS_MIRRORED &&
+            src_ss[1].axis == GGML_BACKEND_SPLIT_AXIS_MIRRORED &&
+            src_ss[2].axis == GGML_BACKEND_SPLIT_AXIS_MIRRORED) {
+        return {GGML_BACKEND_SPLIT_AXIS_MIRRORED, {0}, {1}, 1};
+    }
     GGML_ASSERT(src_ss[0].axis == GGML_BACKEND_SPLIT_AXIS_2);
```

## With that: Flash-Next Q2 coherent on 3 and 4 devices

**4 devices** —
`llama-server -m Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf -ngl 99 -sm tensor -c 4096 --port 8087 -np 1`

```
' Paris. Paris is the most populous city in France, with a population of 2.1 million people.
  It is also the most visited city in the world, with over 30 million tourists'
```

**3 devices** (`CUDA_VISIBLE_DEVICES=0,1,2`, `-ngl 20` to fit) —

```
' Paris. The capital of Germany is Berlin. The capital of Italy is Rome. ...'
```

### Per-card VRAM, four devices

| | `c232282aa` (split, garbage) | `d929da17b` + FA fix (mirrored, correct) |
|---|---|---|
| MiB/card | 13233 / 13263 / 13233 / 13233 | **13603 / 13633 / 13603 / 13603** |

Mirroring costs **~370 MiB/card** — 12 of 48 layers, experts still split. Cheap, as you intended.

## Throughput — worth knowing before anyone optimises for this

Now that output is correct, this is the first valid comparison I have:

| mode | 4-device |
|---|---|
| `-sm layer` | **15.85 tok/s** (pipelined; util bursts then 0/0/0/0) |
| `-sm tensor` | **6.20 tok/s** (all four cards 22-23% concurrently) |

Tensor split is **2.5x slower** here. Per-layer all-reduce across 48 layers on a box with two
NUMA domains and no NVLink (`GPU0<->GPU1 PHB`, `GPU2<->GPU3 PHB`, cross `SYS`). I'm retracting my
earlier "1.5-3x headroom" guess for this topology — it was never measured, and now it's
contradicted. Might still hold where there are peer links.

## `test-llama-archs` at 3 and 4 devices — still aborts, but I think it's the fixture

qwen3next still fails before reaching its Meta row. Instrumented:

```
RATIO mismatch: op=CONCAT dst=conv_input-0(axis=1) j=0
                src[1]=qkv_mixed_transposed-0(axis=1)
                ne[j]=128 nr0=1 src_ne=768 sum=0 dst_ne=768
```

`sum=0` is a zero-width slice on device 0 — but on the **linear-attention** path, which your fix
excludes via `!hparams.is_recr(tc.il)`.

The synthetic model looks like the reason. `test-llama-archs` builds qwen3next with
`ssm_d_state=128`, `ssm_n_group=2`, `ssm_dt_rank=n_head=2`, so key_dim=256, conv_dim=**768** —
matching `src_ne`/`dst_ne` exactly. At granularity 128 the key segment has only **2 splittable
units**, so it goes zero-width at >= 3 devices. Real Flash-Next has key_dim=2048 at granularity
256 = **8 units**, which is why the real model splits 4 ways fine.

So it's the same "units < devices" rule, one level down, and the fixture is just too small to
survive 3-way splitting. I don't think the arch test can pass at >= 3 devices until either the
fixture dims grow or the linear path mirrors when undersubscribed. Your call which — but I'd
flag that growing the fixture is the cheaper one and doesn't change shipping behaviour.

## DS4, lower priority as you said

Still broken on `c232282aa`, and it's a different problem. It now loads and reaches warm-up
(progress — in August on `8a891f4b5` it aborted during allocation), then dies at
`handle_set_rows`. Instrumented:

```
SET_ROWS split mismatch: dst=cache_k_l0 (view)
  src0 = kv-0 (view)      axis=10  (MIRRORED — the values being written)
  src2 = cache_k_l0       axis=0   (split on AXIS_0 — the destination)
```

It's the **main** KV cache, not the indexer. `cache_k_l0` matches `pattern_kv_cache` -> AXIS_0,
while the values written into it are mirrored. Given DS4 is MLA with `head_count_kv = 1` and a
shared latent KV, there's nothing per-head to split — and the split-state already mirrors the
corresponding weights (`pattern_ds4_q_a_kv_weight` -> MIRRORED, "column split would split the
norm row"). The weights are mirrored but the cache they feed is not.

One dead end, recorded so you don't repeat it: I guessed the lightning-indexer cache first, since
`llama-kv-cache-dsv4.cpp` builds `kv_lid` with no `name_tag` (so it's named `cache_k_l*`), and
`"idx_"` is passed from exactly one place in the tree — `llama-memory-hybrid-idx.cpp:58`. I
tagged it, rebuilt, reran: **no change**. The diagnostic above is what identified the real one.

Also worth noting `-ts` ratios matter independently of device count — uneven `-ts 3,4,4,1` fails
earlier (`:1038`, the divisibility assert) than even `-ts 1,1,1,1` (`:730`).

Happy to test whatever you push next on 3 and 4 cards.
