# `d929da17b` on 4x P100 — real models fixed (with one addition), synthetic test still fails

**2026-08-28**, `.194`, 4x Tesla P100-PCIE-16GB sm_60, `GGML_CUDA_ALLREDUCE=internal`,
`TheTom/llama-cpp-turboquant` @ **`d929da17b`** ("fix: mirror undersubscribed GQA attention").

Tom's fix: when a dense (non-recurrent) layer has `n_head_kv(il) < n_devices`, the attention
tensors become `GGML_BACKEND_SPLIT_AXIS_MIRRORED`; linear-attention and MoE/FFN stay split.

## Headline

`d929da17b` **alone still fails** — Flash-Next now *aborts* where `c232282aa` produced garbage.
It needs **one additional 8-line change** to `handle_flash_attn_ext`. With that, both real-model
checks pass.

## 1. Flash-Next Q2, `-sm tensor` — the abort, and the fix

On `d929da17b` as pushed:

```
ggml-backend-meta.cpp:748 GGML_ASSERT(src_ss[0].axis == GGML_BACKEND_SPLIT_AXIS_2) failed
```

`handle_flash_attn_ext` requires Q/K/V split on axis 2 (by head). Tom's fix now delivers them
**MIRRORED**, and the handler has no mirrored path — so mirroring dense attention immediately
breaks flash attention.

**This is on the critical path for every tensor-split run**, not an edge case. llama.cpp
force-enables FA under tensor split:

```
llama_init_from_model: enabling flash_attn since it is required for SPLIT_MODE_TENSOR
```

The precedent is 12 lines below in the same file: `handle_gated_delta_net` already has an
all-mirrored early-out. Adding the same shape:

```cpp
auto handle_flash_attn_ext = [&](const std::vector<ggml_backend_meta_split_state> & src_ss) -> ggml_backend_meta_split_state {
    // Undersubscribed GQA (n_head_kv < n_devices) mirrors the whole attention subgraph, so
    // Q/K/V arrive MIRRORED rather than split by head. Mirror the output too.
    if (src_ss[0].axis == GGML_BACKEND_SPLIT_AXIS_MIRRORED &&
            src_ss[1].axis == GGML_BACKEND_SPLIT_AXIS_MIRRORED &&
            src_ss[2].axis == GGML_BACKEND_SPLIT_AXIS_MIRRORED) {
        return {GGML_BACKEND_SPLIT_AXIS_MIRRORED, {0}, {1}, 1};
    }
    GGML_ASSERT(src_ss[0].axis == GGML_BACKEND_SPLIT_AXIS_2);
    ...
```

### Result: coherent on both 3 and 4 devices

**4 devices**, exact command:

```
llama-server -m .../Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf \
  -ngl 99 -sm tensor -c 4096 --port 8087 -np 1
```

```
ready after 231s
vram: 13603 / 13633 / 13603 / 13603 MiB
util: 23 / 22 / 23 / 22 %   (sustained, all four)
GEN : ' Paris. Paris is the most populous city in France, with a population of 2.1 million
        people. It is also the most visited city in the world, with over 30 million tourists'
6.20 tok/s @ 40 tok, 6.20 @ 80
```

**3 devices** (`CUDA_VISIBLE_DEVICES=0,1,2`, `-ngl 20` so it fits):

```
vram: 7459 / 7089 / 7089 MiB
GEN : ' Paris. The capital of Germany is Berlin. The capital of Italy is Rome. ...'
3.37 tok/s @ 40 tok
```

### Per-card VRAM, 4-device, before vs after mirroring

| | `c232282aa` (split, **garbage**) | `d929da17b` + FA fix (mirrored, **correct**) |
|---|---|---|
| VRAM/card | 13233 / 13263 / 13233 / 13233 | **13603 / 13633 / 13603 / 13603** |

Mirroring the dense attention weights and cache costs **~370 MiB per card** — 12 of 48 layers,
and the expert tensors (which dominate) stay split. Cheap.

## 2. Throughput: tensor split is **slower** than layer split here

Now that the output is correct, this is the first *valid* comparison:

| mode | 4-device | notes |
|---|---|---|
| `-sm layer` | **15.85 tok/s** | pipelined, cards take turns (util bursts then 0/0/0/0) |
| `-sm tensor` | **6.20 tok/s** | all four cards at 22-23% concurrently |

**2.5x slower.** Tensor parallelism all-reduces per layer across 48 layers, and this box has two
NUMA domains with no NVLink (`GPU0<->GPU1 PHB`, `GPU2<->GPU3 PHB`, cross-domain `SYS`). The
earlier "1.5-3x headroom" estimate is now **contradicted by measurement** on this topology.
It may still hold on a box with peer links.

## 3. `test-llama-archs` at 3 and 4 devices — still fails, and it is a fixture artifact

qwen3next still aborts before its Meta row at both 3 and 4 devices, at the ratio assert. I
instrumented it:

```
RATIO mismatch: op=CONCAT dst=conv_input-0(axis=1) j=0
                src[1]=qkv_mixed_transposed-0(axis=1)
                ne[j]=128 nr0=1 src_ne=768 sum=0 dst_ne=768
```

`sum=0` — `qkv_mixed_transposed` gets a **zero-width slice on device 0**. But this is the
**linear-attention (recurrent)** path, which Tom's fix deliberately excludes
(`!hparams.is_recr(tc.il)`).

**And the synthetic model is the reason.** `test-llama-archs` builds qwen3next with
`ssm_d_state = 128`, `ssm_n_group = 2`, `ssm_dt_rank = n_head = 2`:

- key_dim = 128 x 2 = 256, value_dim = 256, conv_dim = 2(256) + 256 = **768** — matches
  `src_ne = 768` / `dst_ne = 768` exactly.
- granularity 128 -> key segment has **256/128 = 2 splittable units** -> zero-width at >= 3 devices.

The **real** Flash-Next model has key_dim = 2048 at granularity 256 = **8 units**, which splits
4 ways cleanly — which is exactly why the real model works and the fixture does not.

So the same "units < devices" rule governs the linear path too; the synthetic model is simply
too small to survive 3-way splitting. **The arch test cannot pass at >= 3 devices until either
the fixture dimensions grow, or the linear path also mirrors when undersubscribed.** This is a
test-fixture limitation, not evidence against the fix.

## 4. Summary against Tom's three asks

| ask | result |
|---|---|
| `test-llama-archs` at 3 and 4 devices, qwen3next reaches + passes Meta | ❌ **still aborts** — cause identified above; fixture-size artifact on the *linear* path |
| Flash-Next Q2 `-sm tensor` coherent on 3 and 4 devices | ✅ **coherent on both** — but requires the `handle_flash_attn_ext` addition |
| per-card VRAM for the 4-device Q2 run | ✅ 13603 / 13633 / 13603 / 13603 MiB (+~370 MiB/card vs split) |

---

# CORRECTION (same day): "tensor split is slower on this topology" was WRONG

I generalised from one model. Mark pushed back — he remembered tensor split being ~1.6x *faster*
on 27B. He was right, and the historical receipts confirm it.

## Apples-to-apples replication of `bench_2v4.sh`

Same model (`Qwen3.8-27B-Q6_K`), same tool (`llama-bench -ngl 99 -p 512 -n 128 -r 3`), same
`GGML_CUDA_ALLREDUCE=internal`, clocks pinned 1063 MHz / 150 W. Historical numbers are from
2026-08-21 using `llama_stock/build_puzzle`; "today" is the PR324 build at `d929da17b` + the
flash-attn mirror patch.

| arm | historical | today | verdict |
|---|---|---|---|
| L2 — 2 GPU, `-sm layer` | 7.70 ± 0.00 | **7.83 ± 0.00** | +1.7%, no regression |
| T2a — 2 GPU, `-sm tensor` | 13.00 ± 0.02 | **13.20 ± 0.01** | +1.5%, no regression |
| T4 — 4 GPU, `-sm tensor` | 15.34 ± 0.05 | **12.80 ± 1.20** ... then 12.56, **15.83**, **15.75** | **bistable** |

**There is no regression.** On 27B dense, tensor split is ~1.7x faster than layer split
(13.20 vs 7.83 at 2 GPUs), exactly as Mark remembered.

## The 4-way arm is bistable, which is what made it look like a regression

Four unbound T4 runs: **12.80, 12.56, 15.83, 15.75** — two distinct modes, ~12.6 and ~15.8, not
a spread. A single sample lands in either. The first sample I took happened to be the slow mode,
and `llama-bench`'s own `± 1.20` (vs `± 0.05` historically, **24x larger**) was the tell I should
have chased before reporting anything.

`bench_2v4.sh` runs L2/T2a/T2b under `numactl` but leaves **T4 unbound** (`numa="-"`), because
4 GPUs span both domains. Binding it removes the slow mode:

| binding | runs |
|---|---|
| none | 12.80, 12.56, 15.83, 15.75 — **2 of 4 slow** |
| `numactl --interleave=all` | 15.35, 14.68 |
| `numactl --cpunodebind=0 --membind=0` | 15.88, 15.21 |

**4 of 4 bound runs >= 14.68; 2 of 4 unbound runs at ~12.6.** Mechanistically sensible: with
GPU0/1 on NUMA 0 and GPU2/3 on NUMA 1, an unbound process lands on whichever socket the
scheduler picks, changing host-memory and PCIe locality for the per-layer all-reduce.

n=4 per condition — suggestive, not settled. But enough that **4-way tensor-split numbers on
`.194` must be NUMA-bound and repeated**, never single-shot.

## So why IS Flash-Next slower under tensor split?

Both things are true, and the difference is the model, not the box:

| model | `-sm layer` | `-sm tensor` (4 GPU) |
|---|---|---|
| Qwen3.8-27B (dense, 27B active) | 7.83 (2 GPU) / 11.14 (4 GPU) | **15.8** — faster |
| Qwen3.8-Flash-Next (MoE, **6B active**) | **15.85** | 6.20 — 2.5x slower |

Flash-Next has only ~6B active parameters and `n_ff_exp = 640`. Split 4 ways that is a
**160-wide expert matmul** per device — far too small to keep a P100 busy, while still paying a
per-layer all-reduce across 48 layers. Tensor split trades communication for parallel compute;
Flash-Next has very little compute per layer to trade. 27B dense has ~4.5x the active parameters
and `n_embd = 5120`, so the split matmuls stay large enough to win.

**Corrected claim:** tensor split is a large win on dense models on this box and a large loss on
this sparse MoE. The topology is not the deciding factor — the active-parameter count per layer
is. The earlier "1.5-3x headroom" estimate stands for dense models (measured 1.7x) and is wrong
for Flash-Next.

## Process failure

I reported a throughput comparison from **one sample per condition**, on the arm with 24x the
variance, and generalised it from one model to "this topology". Three guards that would each have
caught it: repeat any run whose reported error bar jumps; never generalise a performance claim
across model families from a single family; check the historical receipts before contradicting
them — `bench_2v4.log` was on disk the whole time. See AFM-28.
