# Pastable — DS4 tensor-split test results for Jabba (`42974d12`)

Source: `DS4_TENSORSPLIT_42974d12.md`. Logs on `.194` at `~/ds4_tsplit/`, `~/ds4_diag/`,
`~/sanity_check/`.

---

Tested on the quad-P100 box. **Your patch clears the load gate — DS4 now allocates every
weight buffer under `-sm tensor`, where before it asserted at `llama-model.cpp:416`.** It
then hits a second assert at warmup decode, which is the "secondary meta-split assertion"
you predicted. Instrumented it to name the tensor:

```
ggml-backend-meta.cpp:541: GGML_ASSERT(src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_0) failed

PERROW_DIAG: op=RMS_NORM dst='norm-0' ne=[1024,2,1,1]
PERROW_DIAG:   src[0]='qr-0' axis=0 ne=[1024,2]
```

`handle_per_row`, layer 0, `ne[0]=1024` = DS4's `q_lora_rank`. Call path is
`common_init_from_params → llama_decode → process_ubatch → ggml_gallocr_alloc_graph →
ggml_backend_meta_buffer_init_tensor → handle_per_row`, so it is the warmup decode, after a
full successful load.

**Cause — the pattern is catching the low-rank down-projections.** `src/models/deepseek4.cpp:831`:

```cpp
ggml_tensor * qr = build_lora_mm(layer.wq_a, cur);   // attn_q_a -> qr, ne[0] = q_lora_rank
cb(qr, "qr", il);
qr = build_norm(qr, layer.attn_q_a_norm, nullptr, LLM_NORM_RMS, il);   // <-- asserts here
ggml_tensor * q = build_lora_mm(layer.wq_b, qr);     // attn_q_b
```

`pattern_ds4_qkv_weight` = `blk\.\d*\.attn_(q_[ab]|kv)\.weight` assigns `AXIS_1` to
everything it matches, including `attn_q_a`. Column-splitting a weight splits its output
activation along ne[0], and the very next op RMS-normalises across ne[0] — so `handle_per_row`
is right to refuse.

**Two instances, not one.** The kv path is identical at `deepseek4.cpp:856`:

```cpp
ggml_tensor * kv = build_lora_mm(layer.wkv, cur);    // attn_kv (LLM_TENSOR_ATTN_KV, :95)
kv = build_norm(kv, layer.attn_kv_norm, nullptr, LLM_NORM_RMS, il);
```

Same regex matches `attn_kv.weight`, so fixing only `q_a` will move the assert here.

The direction I would try: `q_a` and `kv` are down-projections immediately followed by
per-row norms, so they want MIRRORED rather than column-split; only the up-projections
`q_b` / `kv_b` are safely `AXIS_1`. That means splitting your one pattern into two. Your call
though — you know the meta-split code better than I do, and I have not tried it.

**One caveat worth stating plainly: this does not tell you the split is numerically correct.**
No token has been generated under `-sm tensor` at any setting, so nothing is known about
output quality either way. Previous experience on this fleet: a turbo3 KV bug loaded fine and
ran fine and quietly emitted garbage (gzip ratio 0.175–0.347 against a 0.51 control) — nothing
asserted. Worth a coherence check once it decodes, not just a clean startup.

## The good news: the memory wall moved a rung

`-ncmoe` floor went **40 → 30**. Same allocation phase both sides (`alloc_tensor_range`,
weight loading), so it is a like-for-like comparison:

| `-ncmoe` | layer-split, largest single-device request | tensor-split |
|---|---|---|
| 30 | **20,587 MiB → OOM** | **fits** (≤16,269 MiB) |
| 20 | 28,251 MiB → OOM | 16,412 MiB → OOM |

At `-ncmoe 20` the largest request drops 28,251 → 16,412 MiB — about **1.72×**, not the ~4×
full sharding across four cards would give. So attention is being split and the routed
experts appear not to be. Enough to clear one rung; at 20 it misses by 143 MiB. If the expert
tensors are meant to be in the split set too, that gap is where it shows.

## No regression on the working path

Clean `42974d12`, no local patches, `version: 10245`:

```
DS4-Flash IQ1_S, -sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40
  -> 2.20 t/s, gzip 0.4649, CJK 0, vram [3491, 2641, 4507, 4529]
```

Baseline before your patch was 2.16 t/s / gzip 0.469–0.567, so layer-split is untouched.

## Two small things

**Your suggested line omits `-fit off`**, which prints
`llama_params_fit is not implemented for SPLIT_MODE_TENSOR, abort`. It is only a warning and
the run continues to the same decode assert — but it looks alarming and reads like the failure
if you are not expecting it. Might be worth a cleaner message, or implementing the
tensor-split path in the fitter.

**The commit you posted, `04ccc10da`, does not resolve** — force-push or a local hash. The one
matching your description is `42974d12` on `giveen/feature/turboquant-kv-cache-rebase`, and
that is what everything above was run against.

Setup for the record: 4× Tesla P100-PCIE-16GB (sm_60, 16,269 MiB each, 1063 MHz / 150 W),
2× Xeon E5-2650 v3, 60 GiB DDR4-2133, `unsloth/DeepSeek-V4-Flash-0731-GGUF` UD-IQ1_S
(82.5 GB), `CMAKE_CUDA_ARCHITECTURES=60`. All arms `-c 8192 -ngl 99 -ts 3,4,4,1 -fa on`.
Happy to run anything else — the box is idle and every failure here is deterministic.
