# Verification of `c232282aa` on 4x P100 (sm_60)

**2026-08-28**, `.194`: 4x Tesla P100-PCIE-16GB, dual Xeon E5-2650 v3, 64 GB DDR4.
`TheTom/llama-cpp-turboquant` @ **`c232282aa`** ("fix: complete qwen4exp integration"),
clean checkout, incremental rebuild verified (19 objects rebuilt, `libllama.so.0` relinked
18:23:15Z; object mtimes newer than sources).

Requested by Tom on PR #324. `GGML_CUDA_ALLREDUCE=internal` pinned for every run below.

## 1. `test-llama-archs` — qwen4exp Meta row

**The qwen4exp fix works on sm_60.** At 2 devices the whole suite is clean:

```
|        qwen4exp|                     Tesla P100-PCIE-16GB|   MoE|  OK (4.40e-14)|       OK|
|        qwen4exp|                     Tesla P100-PCIE-16GB|   MoE|  OK (4.40e-14)|       OK|
|        qwen4exp|Intel(R) Xeon(R) CPU E5-2650 v3 @ 2.30GHz|   MoE|  OK (0.00e+00)|       OK|
|        qwen4exp|                                     Meta|   MoE|  OK (4.40e-14)|     SKIP|
```

`CUDA_VISIBLE_DEVICES=0,1` — **0 asserts, 0 CUDA errors across the entire suite.**

## 2. But the suite aborts at **qwen3next**, not qwen4exp, when n_devices >= 3

| devices | result |
|---|---|
| `0,1` (2) | **entire suite passes**, incl. qwen4exp Meta |
| `0,1,2` (3) | aborts at **qwen3next / Meta / MoE** |
| `0,1,2,3` (4) | aborts at **qwen3next / Meta / MoE** |

```
ggml-backend-meta.cpp:1050: GGML_ASSERT(
    split_state.ne[j]*split_state.nr[0] * tensor->src[i]->ne[src_ss[i].axis]
    == sum * tensor->ne[split_state.axis]) failed
```

Three things worth separating:

- This is **qwen3next**, an architecture that was already supported — not qwen4exp, and not
  something `c232282aa` introduced. It reproduces identically on `d74823a0c`.
- It is a **different assert** from the one qwen4exp used to hit
  (`llama-model.cpp:583`, the fused-QKV width check).
- Because qwen3next is enumerated **before** qwen4exp, this abort makes the qwen4exp Meta row
  **unreachable** at >= 3 devices. That is why the 2-device run is the one that answers Tom's
  question.

The threshold is 2-vs-3, not a power-of-two effect. Consistent with the split arithmetic
producing a zero-width or non-proportional slice once the device count stops dividing the
segment cleanly — the assert multiplies `split_state.ne[j]`, so any device receiving a
zero-width slice fails the equality.

## 3. NCCL still fails on the cross-socket hop

Without `GGML_CUDA_ALLREDUCE=internal`, the 4-device run dies earlier and elsewhere:

```
ggml-cuda.cu:110: CUDA error: unhandled cuda error
  current device: 2, in ggml_backend_cuda_comm_allreduce_nccl at ggml-cuda.cu:1105
  ncclAllReduce(...)
```

`nvidia-smi topo -m`: `GPU0<->GPU1 PHB`, `GPU2<->GPU3 PHB`, cross-domain `SYS`. No NVLink.
The env var remains mandatory on this box; this is unchanged and not a regression.

## 4. Real-model compute buffers at `-ngl 44` — **every mismatch is gone**

`Qwen3.8-Flash-Next-UD-IQ4_XS`, `-ngl 44 -sm layer -np 1 -c 4096 -lv 5`,
`n_slots = 1, kv_unified = 'false'` (identical context config to the `d74823a0c` baseline).
Values from the `~llama_context` destructor.

| backend | `d74823a0c` actual vs expected | `c232282aa` actual vs expected |
|---|---|---|
| CUDA0 | *(no warning — matched)* | **1001.5005** vs 1001.5005 ✅ |
| CUDA1 | 146.7911 vs 139.0157 ❌ | **139.0157** vs 139.0157 ✅ |
| CUDA2 | 149.8038 vs 144.0157 ❌ | **144.0157** vs 144.0157 ✅ |
| CUDA3 | 149.8038 vs 144.0159 ❌ | **144.0159** vs 144.0159 ✅ |
| CUDA_Host | 29.7715 vs 14.8692 ❌ | **14.4005** vs 14.4005 ✅ |

All five now log at DEBUG as `matches expectation`; **zero WARN lines**. This is the **real model only** — I did not exercise the synthetic estimator path where you said warnings persist. The all-layer Q2 run in section 5 also matches on all five buffers **with both fused GDN paths enabled**, whereas this `-ngl 44` run has chunked GDN auto-disabled (layer 0 on CPU) — so the accounting is clean on both paths, not just one configuration.

Note the direction: the three CUDA *expectations* are unchanged to the fourth decimal
(139.0157 / 144.0157 / 144.0159). The estimator did not move — the **actual** allocations came
down to meet it. `CUDA_Host` is the one where both sides moved (expectation 14.8692 -> 14.4005,
actual 29.7715 -> 14.4005), consistent with PLE recurrent history no longer being packed into
the delta-net state row.

Per-card VRAM while loaded: 14767 / 13903 / 14311 / 13991 MiB. Generation coherent
(`" Paris. The capital of Germany is Berlin. ..."`), 6.38 tok/s at 40 tokens,
5.34 tok/s at 80. Clocks pinned 150 W / P100 default (405 MHz idle, autoboost under load).

### Methodology note — why an earlier pass of this looked "clean" and was not

My first two `-ngl 44` runs emitted **no** compute-buffer lines at all and I nearly reported
that as "fixed". It was an artefact: `~llama_context` logs matches at **DEBUG**, and
`common/log.h:24` sets `LOG_LEVEL_DEBUG = 5` while I was running `-lv 3`
(`common/log.cpp:85` drops DEBUG below that threshold). Absence of WARN was not evidence of
matching — it was evidence of nothing. Only the `-lv 5` run above distinguishes the two. Also
worth flagging for anyone reproducing: the first run defaulted to `-np 4`
(`n_slots = 4, kv_unified = 'true'`), which is a different context configuration and not
comparable to the baseline; `-np 1` is required.

## 5. All-layer Q2 smoke test — passes

`Qwen3.8-Flash-Next-UD-Q2_K_XL`, `-ngl 99 -sm layer -np 1 -c 4096`. Coherent, all 48 layers
GPU-resident, **all five compute buffers match** (191.0630 / 328.0630 / 328.0630 / 328.0635 /
26.1955 MiB, zero WARN). Both fused GDN paths enabled (`autoregressive` + `chunked`).
15.85 tok/s @ 40 tokens, 14.95 @ 80 — consistent with the previously recorded 15-16 tok/s
layer-split floor. VRAM 13415 / 12387 / 12387 / 11755 MiB.

(At `-ngl 44` the chunked GDN is *disabled* — `layer 0 is assigned to device CPU but fused
Gated Delta Net (chunked) is assigned to device CUDA0`. Worth knowing when comparing the two.)

## 6. `-sm tensor` now loads — and is silently wrong at >= 3 devices

**It no longer aborts.** `-ngl 99 -sm tensor` on 4x P100 loads, and the split is real:

| | layer split | tensor split |
|---|---|---|
| VRAM per card | 13415 / 12387 / 12387 / 11755 | **13233 / 13263 / 13233 / 13233** |
| GPU util during decode | 16/15/20/21 then 0/0/0/0 (bursty, cards take turns) | **21/22/22/22 sustained on all four** |
| output | coherent | **`////////////////////////////////////////`** |
| tok/s | 15.85 | 6.14 |

Even VRAM and four cards busy simultaneously is genuine tensor parallelism. But the numerics
are wrong, and **nothing asserts** — it just emits garbage.

### Controlled device-count sweep

Same model, same `-ngl 20`, same `-sm tensor`, `-np 1`. **Only the device count varies:**

| devices | VRAM | output |
|---|---|---|
| `0,1` | 10249 / 10067 | ✅ `" Paris. The capital of Germany is Berlin. ..."` |
| `0,1,2` | 7337 / 6945 / 6945 | ❌ `"////////..."` |
| `0,1,2,3` | 5407 / 5569 / 5773 / 5387 | ❌ `"////////..."` |

This is the **same 2-vs-3 threshold** as the synthetic `test-llama-archs` abort in section 2 —
two manifestations of one bug. Synthetic trips a hard assert (via qwen3next, enumerated first);
the real qwen4exp model produces silent garbage.

### Mechanism — dense attention has only **2** splittable units, because `head_count_kv = 2`

Derived from the code and the GGUF header, not instrumented, but it predicts the threshold
exactly and covers two independent tensors.

The split unit for dense attention is the **KV group**, and this model has
`qwen4exp.attention.head_count_kv = 2`. With `head_count = 24` and `key_length = 256`:
`n_gqa = 12`, `n_embd_q = 12 * 256 = 3072`.

| tensor | `ne[axis]` | granularity | = splittable units |
|---|---|---|---|
| `blk.N.attn_q.weight` | 12288 | `lcm(2*n_embd_q, 256)` = **6144** | 12288/6144 = **2** |
| `blk.N.attn_k.weight` | 512 | `granularity_q / n_gqa` = **256** | 512/256 = **2** |

Both land on exactly `n_head_kv` = 2. Running the splitter's `high -= high % g_s`:

| n_devices | `attn_q` | `attn_k` |
|---|---|---|
| 2 | 6144 / 6144 | 256 / 256 |
| 3 | **0** / 6144 / 6144 | **0** / 256 / 256 |
| 4 | **0** / 6144 / **0** / 6144 | **0** / 256 / **0** / 256 |

**At >= 3 devices there are fewer splittable units than devices, so some device necessarily
receives `ne = 0`.** `ggml-backend-meta.cpp:1050` multiplies `split_state.ne[j]`, so a
zero-width slice makes the left-hand side 0 and fails the equality.

**The granularity is not too large — it is load-bearing.** 6144 is `granularity_q` doubled for
qwen4exp's `[q|gate]` packing, and its job is to keep a whole KV group on one device. Lowering
it would split a KV group across cards and break the attention math — producing garbage tokens,
i.e. the same symptom. The fix belongs in how a zero-width slice is handled (or refused), not in
the granularity computation.

This also means **dense attention on this model cannot be split more than 2 ways at all**,
independent of any bug. The 36 linear-attention layers are not so constrained (`ssm_n_group` 16,
`ssm_dt_rank` 48), which is consistent with the even VRAM observed.

The arch wiring in `c232282aa` is confirmed correct at 2 devices; this is a separate,
pre-existing splitter issue.

## 7. Prediction scoring

Logged in `PREDICTIONS_tensor_split_patch.md` **before** these runs.

| # | prediction | outcome |
|---|---|---|
| P1 | loads without aborting in `get_split_state` | ✅ **confirmed** at 2/3/4 devices |
| P2 | given P1, generation is coherent | ❌ **falsified at >= 3 devices**; holds at 2 |
| P3 | expert gate/up split 128/128/128/256 | ⬜ untested (needs split-state instrumentation) |
| P4 | dense `attn_q` splits 0/6144/0/6144 on 4 devices | ⚠️ not instrumented, but the same arithmetic **predicts the observed 2-vs-3 threshold** |
| P5 | 36 linear layers split evenly | ~ consistent with the even VRAM, not isolated |
| P6 | throughput beats the 15-16 tok/s layer-split floor | ⬜ **untested** — see below |
| P7 | `test-llama-archs` passes qwen4exp | ✅ **confirmed** at 2 devices; unreachable at >= 3 |

**P6 cannot be scored from these runs, in either direction.** The 4-device tensor-split run
produced 6.14 tok/s, but it emitted `////////` — a run with wrong numerics is not a measurement
of decode throughput, and may not even traverse the same kernels. The 2-device coherent run
(3.4 tok/s) had only 20 of 48 layers on GPU and is not comparable to the `-ngl 99` layer-split
floor either.

**No valid tensor-split throughput measurement exists on this box yet.** The "1.5-3x headroom"
estimate in `RESULT_TENSOR_SPLIT_BLOCKED.md` therefore remains **unmeasured** — I have no
datapoint for or against it. Recording a falsification here would be the same over-claim as
recording a confirmation, with the sign flipped.

## 8. The rule, confirmed in both directions

The mechanism in section 6 predicts more than a failure — it predicts exactly *when* tensor split
is correct. Dense attention splits into exactly `head_count_kv` units, so:

> **For architectures that split dense attention by KV group** (the standard GQA path —
> qwen35 / qwen3next / qwen4exp), **`-sm tensor` is correct iff `n_devices <= head_count_kv`.**
>
> **Scope caveat:** this does *not* generalise to MLA. `deepseek4` has `head_count_kv = 1`
> but never reaches this path — the split-state gives it dedicated patterns
> (`attn_q_a`/`attn_kv` MIRRORED, `attn_q_b` paired to `attn_output_a`). See below.

Tested by holding the binary (`c232282aa`), the box (4x P100), and the flags
(`-ngl 99 -sm tensor -np 1 -c 4096`) fixed and varying only the model:

| model | arch | `head_count_kv` | 2 dev | 3 dev | 4 dev |
|---|---|---|---|---|---|
| synthetic `test-llama-archs` (`n_head = 2`, `head_count_kv = n_head`) | qwen3next | **2** | ✅ pass | ❌ abort | ❌ abort |
| Qwen3.8-Flash-Next-UD-Q2_K_XL | qwen4exp | **2** | ✅ coherent | ❌ garbage | ❌ garbage |
| Qwen3.8-27B-UD-IQ4_XS | qwen35 | **4** | — | — | ✅ **coherent** |

The 27B run is the important one, because the rule predicted a **success** and got one:

```
## vram: 0, 3701 MiB | 1, 3701 MiB | 2, 3701 MiB | 3, 3701 MiB     <- exactly even
## util: 0, 56 % | 1, 55 % | 2, 51 % | 3, 55 %                     <- all four concurrent
## GEN: ' Paris.\nThe capital of Germany is Berlin. ...'
## TPS: 15.39 tok/s (40 tok), 15.41 tok/s (80 tok)
```

`12288 / (2 * n_gqa * n_embd_head_k)` = `12288 / (2*6*256)` = **4** units for the 27B
(`head_count = 24`, `head_count_kv = 4`), so 4 devices get one unit each and nothing is
zero-width. Flash-Next has `head_count_kv = 2`, so the third device onward gets nothing.

This is also **the first valid tensor-split throughput measurement on this box** — the earlier
Flash-Next figure was from a run emitting garbage and is not a measurement. 15.4 tok/s at 4-way
tensor split with all four cards at ~55% is a working tensor parallel decode on P100s.

### Consequence for the fix

The bug is not "3 or more devices". It is **more devices than KV groups**, which is a property of
the model, not of the hardware. A fix has to decide what to do when the unit count runs out —
refuse with a clear error, or fall back to placing the tensor on a subset of devices — but it
must not narrow the granularity, which is what keeps a KV group intact.

### buun's fork carries the same arithmetic

`spiritbuun/buun-llama-cpp` @ `02f8581c6`: the slice-assignment loop in
`llama_meta_device_get_split_state` is **byte-identical** to Tom's, and `get_split_granularity`
differs only by features (buun has DFlash tape patterns; it lacks the `QWEN4EXP` case Tom just
added). So the same `n_devices > head_count_kv` limit should apply there.

buun's "my tensor splitting is different from upstream and should work fine" is **consistent with
this**, not contradicted by it: `.73` has 2 GPUs, and Qwen3.8-27B has `head_count_kv = 4` — both
inside the safe region. **Not measured on buun's fork**: the `test-llama-archs` binary on `.194`
is from 2026-06-27 against 2026-08-22 sources, so a rebuild would be needed to test it.


## 9. Fleet history — was Flash-Next the first model to cross this line?

Nearly, but not quite, and the distinction is worth keeping straight.

Every prior `-sm tensor` run on `.194` falls into one of two groups:

| campaign | model | arch | `head_count_kv` | devices | outcome |
|---|---|---|---|---|---|
| `apex_test.sh`, `dflash2_bench`, `tsspeed_run`, `spec_matrix` | Qwen3.8-27B (Q6_K / UD-IQ4_XS / APEX / DFlash2) | qwen35 | **4** | 4 | worked |
| `bench_2v4.sh` (NUMA-pair A/B) | Qwen3.8-27B-Q6_K | qwen35 | **4** | 2 | worked |
| `ds4_tsplit_run` (2026-08-01, commit `8a891f4b5`) | DeepSeek-V4-Flash UD-IQ1_S | deepseek4 | **1** | 4 (`-ts 3,4,4,1`) | **failed, every arm** |

So the qwen35 work has been sitting **exactly on the boundary the whole time** — 4 cards, 4 KV
groups, `n_devices == head_count_kv`. One fewer KV group, or one more card, and it would have
broken months ago.

**DS4 was the first model to go under the line**, on 2026-08-01, and it also failed under
`-sm tensor` — but with a *different* assert:

```
GGML_ASSERT(src_ss[0].axis != GGML_BACKEND_SPLIT_AXIS_0) failed
```

against `-sm layer -ts 3,4,4,1 -ncmoe 40` = 2.16 t/s as the baseline it was trying to beat.
That was on much older code, and `c232282aa` now carries dedicated DS4 patterns
(`pattern_ds4_q_a_kv_weight` -> MIRRORED, `pattern_ds4_q_b_weight` -> paired with
`attn_output_a`) which did not exist then — plausibly added in response to exactly that failure.

### So the accurate statement

Flash-Next is the first model **on current code** to go under the line, and the first anywhere in
this campaign where the failure is **silent** — DS4 aborted loudly, Flash-Next emits `////` and
returns HTTP 200.

### Open question worth one run

**Does DS4 tensor-split work at 4 devices on `c232282aa`?** If the mirrored-`q_a`/`kv` treatment
fixed the under-provisioned case for MLA, that approach may be the template for the GQA path
too. Untested — the DS4-Flash IQ1_S is on `.194`.
