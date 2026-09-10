# DRAFT — PR #324 reply for Mark to review. NOT POSTED.

---

Synced to `c232282aa` on the 4x P100 box (sm_60, dual Xeon E5-2650 v3). Clean checkout, verified
real rebuild. `GGML_CUDA_ALLREDUCE=internal` pinned throughout. All three items below, plus one
thing you'll want to see.

## 1. Qwen4Exp Meta row — passes

```
|        qwen4exp|                     Tesla P100-PCIE-16GB|   MoE|  OK (4.40e-14)|       OK|
|        qwen4exp|                     Tesla P100-PCIE-16GB|   MoE|  OK (4.40e-14)|       OK|
|        qwen4exp|Intel(R) Xeon(R) CPU E5-2650 v3 @ 2.30GHz|   MoE|  OK (0.00e+00)|       OK|
|        qwen4exp|                                     Meta|   MoE|  OK (4.40e-14)|     SKIP|
```

That is with `CUDA_VISIBLE_DEVICES=0,1`. Whole suite clean — 0 asserts, 0 CUDA errors.

**With 3 or 4 devices visible the suite never reaches qwen4exp.** It aborts earlier at
**qwen3next**:

```
ggml-backend-meta.cpp:1050: GGML_ASSERT(
    split_state.ne[j]*split_state.nr[0] * tensor->src[i]->ne[src_ss[i].axis]
    == sum * tensor->ne[split_state.axis]) failed
```

2 devices pass, 3 and 4 fail. Reproduces identically on `d74823a0c`, so it predates your commit
and isn't qwen4exp-specific. If your local box is 1-2 GPUs that would explain the difference
from your run.

## 2. Real model `-ngl 44` compute buffers — every mismatch gone

`Qwen3.8-Flash-Next-UD-IQ4_XS`, `-ngl 44 -sm layer -np 1 -c 4096`, `n_slots = 1`,
`kv_unified = false` (same context config as the earlier baseline).

| backend | `d74823a0c` | `c232282aa` |
|---|---|---|
| CUDA0 | (matched) | **1001.5005** vs 1001.5005 ✅ |
| CUDA1 | 146.7911 vs 139.0157 ❌ | **139.0157** vs 139.0157 ✅ |
| CUDA2 | 149.8038 vs 144.0157 ❌ | **144.0157** vs 144.0157 ✅ |
| CUDA3 | 149.8038 vs 144.0159 ❌ | **144.0159** vs 144.0159 ✅ |
| CUDA_Host | 29.7715 vs 14.8692 ❌ | **14.4005** vs 14.4005 ✅ |

Zero WARN lines; all five log `matches expectation` at DEBUG. **Real model only** — I didn't exercise the synthetic estimator path you mentioned, so I can't speak to those warnings.

Worth noting the direction: the three CUDA **expectations are unchanged to four decimals**. The
estimator didn't move — the actual allocations came down to meet it. `CUDA_Host` is the only one
where both sides moved (14.8692 -> 14.4005 expected, 29.7715 -> 14.4005 actual), which is what
I'd expect from PLE history getting its own row.

Reproduction note: these print from `~llama_context` at **DEBUG**, so `-lv 5` is required —
at `-lv 3` a fully-matching run looks identical to a run that never emitted. Also `-np 1`
matters; the default `-np 4` gives `n_slots=4, kv_unified=true` and different buffer sizes.

## 3. All-layer Q2 smoke test — passes

`Q2_K_XL`, `-ngl 99 -sm layer -np 1`. Coherent, both fused GDN paths enabled, 15.85 tok/s.
All five buffers match: 191.0630 / 328.0630 / 328.0630 / 328.0635 / 26.1955 MiB.

Worth connecting to §2: that `-ngl 44` run had chunked GDN **auto-disabled** (*"layer 0 is
assigned to device CPU but fused Gated Delta Net (chunked) is assigned to device CUDA0"*), while this one has **both fused paths enabled** — and both match on all five buffers. So the
accounting is clean on both paths, not just one configuration.

## 4. The thing you'll want: `-sm tensor` loads now, but is silently wrong at >= 3 devices

Good news first — it no longer aborts, and the split is genuinely working:

| | `-sm layer` | `-sm tensor` |
|---|---|---|
| VRAM/card | 13415 / 12387 / 12387 / 11755 | **13233 / 13263 / 13233 / 13233** |
| util during decode | 16/15/20/21 then 0/0/0/0 | **21/22/22/22 sustained** |
| output | coherent | **`////////////////////////////////////////`** |

Even VRAM, four cards busy at once. But garbage out, and **no assert fires**.

I'm deliberately not quoting a tok/s for the tensor-split runs: a run emitting `////////` isn't a throughput measurement. I have no valid tensor-split performance number yet, in either direction.

Controlled sweep — same model, same `-ngl 20`, same `-sm tensor`, only device count changes:

| devices | output |
|---|---|
| 2 | ✅ `" Paris. The capital of Germany is Berlin. ..."` |
| 3 | ❌ `"////////..."` |
| 4 | ❌ `"////////..."` |

Same 2-vs-3 threshold as the `test-llama-archs` abort in §1. I think they're one bug: synthetic
trips the assert, the real model just produces wrong tokens.

### The mechanism — dense attention has only 2 splittable units

From the code plus the GGUF header. It predicts the threshold exactly and covers two independent
tensors.

The split unit here is the KV group, and this model has `attention.head_count_kv = 2`. With
`head_count = 24`, `key_length = 256`: `n_gqa = 12`, `n_embd_q = 3072`.

| tensor | `ne[axis]` | granularity | splittable units |
|---|---|---|---|
| `blk.N.attn_q.weight` | 12288 | `lcm(2*n_embd_q, 256)` = 6144 | **2** |
| `blk.N.attn_k.weight` | 512 | `granularity_q / n_gqa` = 256 | **2** |

Both come out to exactly `n_head_kv` = 2. Running `high -= high % g_s`:

| n_devices | `attn_q` | `attn_k` |
|---|---|---|
| 2 | 6144 / 6144 | 256 / 256 |
| 3 | **0** / 6144 / 6144 | **0** / 256 / 256 |
| 4 | **0** / 6144 / **0** / 6144 | **0** / 256 / **0** / 256 |

At >= 3 devices there are simply fewer splittable units than devices, so some device
necessarily gets `ne = 0` — and `ggml-backend-meta.cpp:1050` multiplies `split_state.ne[j]`,
so a zero slice zeroes the left side and fails.

**To be clear about what I am not suggesting:** the granularity isn't too big. 6144 is
`granularity_q` doubled for the `[q|gate]` packing and its job is to keep a whole KV group on one
device — lowering it would split a KV group across cards and break attention, which produces
garbage tokens, i.e. exactly this symptom. I think the fix is in how a zero-width slice is
handled or refused, not in the granularity.

It also implies dense attention on this model can't be split more than 2 ways regardless, since
there are only 2 KV groups. The 36 linear-attention layers aren't constrained that way
(`ssm_n_group` 16, `ssm_dt_rank` 48), which fits the even VRAM.

Your arch wiring looks correct — it's confirmed good at 2 devices. This reads to me as a
separate, pre-existing splitter issue.

### Confirmed in both directions

The rule this implies is: `-sm tensor` is correct iff `n_devices <= head_count_kv`. Holding the
binary, box and flags fixed and varying only the model:

| model | arch | `head_count_kv` | 2 dev | 3 dev | 4 dev |
|---|---|---|---|---|---|
| synthetic `test-llama-archs` (`head_count_kv = n_head = 2`) | qwen3next | 2 | ✅ | ❌ abort | ❌ abort |
| Flash-Next Q2_K_XL | qwen4exp | 2 | ✅ | ❌ garbage | ❌ garbage |
| Qwen3.8-27B-UD-IQ4_XS | qwen35 | **4** | — | — | ✅ **coherent** |

The 27B is the one that matters, because the rule predicted a *success* and got one — same
binary, same four cards, same flags, only `head_count_kv` differs:

```
vram: 3701 / 3701 / 3701 / 3701 MiB    (exactly even)
util: 56 / 55 / 51 / 55 %              (all four concurrent)
GEN : ' Paris.\nThe capital of Germany is Berlin. ...'
15.39 tok/s @ 40 tok, 15.41 @ 80
```

So the failure isn't "3+ devices" — it's **more devices than KV groups**, a property of the model
rather than the box. Whatever the fix is, it has to handle the unit count running out (refuse, or
place on a subset) rather than shrink the granularity.

Happy to instrument the split state and dump per-device `ne` for the dense Q tensor if that'd
help confirm, or to test any patch on 3 and 4 cards.
