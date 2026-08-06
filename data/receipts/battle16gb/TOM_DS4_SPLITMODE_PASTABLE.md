# Pastable — DS4-Flash split-mode bugs (for Tom, turboquant fork)

Two load-time asserts, deterministic, one-line repros. Source: `DS4_FLASH_P100_LOAD.md`,
logs in `.194:~/ds4_row/`.

---

Ran DeepSeek-V4-Flash on the quad-P100 box against `feature/turboquant-kv-cache`
@ `8a891f4b5` — the DS4 port works, but **both parallel split modes fail at load time**.
Reporting because they look like arch-coverage gaps rather than capacity limits.

**Setup:** 4× Tesla P100-PCIE-16GB (sm_60, CUDA 12.4), `unsloth/DeepSeek-V4-Flash-0731-GGUF`
UD-IQ1_S (82.5 GB, 3 shards). Build: `CMAKE_CUDA_ARCHITECTURES=60`, runtime reports
`ARCHS = 600`. 82.5 GB against 63.5 GiB VRAM, so MoE experts go to CPU via `-ncmoe`.

**What works:**
```
-c 8192 -ngl 99 -sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40
```
Loads in 3m12s, generates coherently, 2.16 t/s decode. No complaints.

---

**Bug 1 — `-sm tensor` asserts at every offload level**

```
-c 8192 -ngl 99 -sm tensor -fit off -fa on -ncmoe 40
```
```
llama_model_loader: tensor overrides to CPU are used with mmap enabled -
                    consider using --no-mmap for better performance
/src/llama-model.cpp:416: GGML_ASSERT(!suffix_fallback.empty()) failed
```

Identical assert at `-ncmoe` **40, 30, 20 and 10**. Fires during model load, before any
buffer allocation — so it is not memory pressure. `-ncmoe 40` loads fine under `-sm layer`,
so the only variable is the split mode.

Looks like tensor-name suffix resolution failing when tensor-split meets CPU-MoE overrides.
I have not tried `-sm tensor` without `-ncmoe` (the model cannot fit without offload here),
so I can't say whether the override is required to trigger it — that may be worth checking
on hardware that fits DS4 natively.

Worth noting `-sm tensor` is otherwise healthy on sm_60 for us: the dual-P100 box ran it
across a six-arm campaign, and buun's `fa8b372e7` tensor-split fix was confirmed on Pascal
there. So this reads DS4-specific rather than Pascal-specific.

---

**Bug 2 — `-sm row` rejects a DS4 attention tensor**

```
-c 8192 -ngl 99 -sm row -fit off -fa on -ncmoe 40
```
```
/ggml/src/ggml-backend.cpp:898: pre-allocated tensor
  (blk.0.attn_output_a.weight (reshaped)) in a buf
```

`attn_output_a` is a DS4 tensor name, and the "(reshaped)" suffix suggests row-split is
hitting a view it cannot re-home. Also a load-time failure.

(At `-ncmoe 30` row-split gets past this and hits a genuine OOM — 16,657 MiB on device 3 —
so that arm is legitimately capacity-bound, unlike bug 1.)

---

---

**Both are the same root cause, and I think it's a tensor-name mismatch in the upstream TP code.**

`src/llama-model.cpp:348`:
```cpp
const std::regex pattern_attn_out_weight ("blk\\.\\d*\\.attn_output.weight");
```

But DS4 has **no** `attn_output` — `src/llama-arch.cpp:465-466` defines it as a *pair*:
```cpp
{ LLM_TENSOR_ATTN_OUT_A, "blk.%d.attn_output_a" },
{ LLM_TENSOR_ATTN_OUT_B, "blk.%d.attn_output_b" },
```

So for a DS4 q/k/v tensor the chain is:

1. matches `pattern_q_weight` (line 425)
2. → `get_tensor_config_impl(AXIS_1, "attn_output.weight", "ssm_out.weight")`
3. `get_tensor("blk.N.attn_output.weight")` → **nullptr** (DS4 has `_a`/`_b`)
4. falls back to `ssm_out.weight` → DS4 has no SSM tensors either
5. `GGML_ASSERT(!suffix_fallback.empty())` fires — line 416

That also explains bug 2: row-split reaches `blk.0.attn_output_a.weight` and has no config
for it, so it surfaces as the pre-allocated-tensor error instead of the assert.

`suffix_fallback` comes from upstream `d6f303004` (#19378, backend-agnostic tensor
parallelism), which predates the DS4 port — so this is upstream TP code that has never seen
DS4's naming, rather than anything the port introduced. Every arch with a split attention
output would hit it.

Naive fix would be widening the pattern to `attn_output(_a|_b)?` and giving DS4-aware suffix
arguments, but you'll know whether `_a` is the right axis-0 reference — I'd be guessing at
which of the pair the q/k/v split should key off.

**Why it matters beyond our box:** with layer-split, taking one more DS4 layer off CPU
demands **20,587 MiB then 28,251 MiB on a single device** — the request size is constant
while the target device moves with `-ts`, which reads like one layer's expert tensors
exceeding a 16 GB card. Row/tensor split is exactly the mechanism that would shard those,
so these two bugs are what stands between a 16 GB-class multi-GPU box and a faster DS4.
Can't confirm that theory while neither mode loads.

`-fit on` also OOMs here (20,255 MiB on device 0) — same indivisible-tensor shape, so no
complaint about the fitter, just noting it does not route around it.

Happy to run anything else on the quad-P100 — it is idle and the repros are deterministic.
