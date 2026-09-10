# IQ2_S 27B on a 16 GB desktop card: it runs, it stays coherent, and llama.cpp's fit lies by 2.4 GiB

**2026-08-18**, control plane **RX 9070 XT (gfx1201, RDNA4, ROCm/HIP)**, `moe-cache-test`
HIP build. Model `Qwen3.8-27B-AD-IQ2_S.gguf` (10.38 GiB file, AtomicChat quant).
**Run on the live desktop session** — Plasma, Chrome, YouTube, Discord, Claude desktop all
open. That is the point: this is the scenario, not a clean room.

Preliminary. Smoke tests and memory accounting, **not** a fidelity panel.

## 1. It runs, and the reasoning is sound

| | |
|---|---|
| prompt | 86-374 t/s |
| generation | **27.9-28.6 t/s** |
| coherence | intact |

Asked why a KV cache grows with context, the model's reasoning correctly identified per-token
K/V vectors, linear growth in sequence length, and the batch/heads/dim factors. On a maths
word problem it computed the net fill rate correctly at every KV setting. **This is not a
model degraded into uselessness by IQ2.**

> ## ⚠️ SECTION 2 IS RETRACTED — the K cache was never turbo (2026-08-28)
>
> **Verified by re-running this exact build and model:** `moe-cache-test/src/build-hip`
> (`giveen/llama-cpp-turboquant`, guard present) with
> `-m Qwen3.8-27B-AD-IQ2_S.gguf -ctk turbo3 -ctv turbo3` emits:
>
> ```
> W llama_kv_cache: auto-asymmetric: GQA ratio 6:1 (n_head=24, n_head_kv=4)
>   — upgrading K from turbo3 to q8_0 to prevent quality degradation.
> ```
>
> Qwen3.8-27B is `n_head 24 / n_head_kv 4` = **GQA 6:1**, exactly the guard's threshold, and
> **all three of `turbo2/3/4` are trigger types**. Every row of the section-2 table therefore
> measured **`q8_0` K + turboN V**, not symmetric turboN.
>
> The paper's catastrophic pairing puts the lossy codec on **K** — the side the GQA broadcast
> amplifies — which is precisely the arm the guard removes. **The registered 0.75 prediction is
> therefore NOT falsified; the test did not exercise the mechanism it was designed to test.**
>
> Sections 1, 3 and 4 (coherence, KV arithmetic, ROCm `hipMemGetInfo`) are **unaffected** —
> none depends on the K codec.
>
> To redo it: set `TURBO_AUTO_ASYMMETRIC=0` and capture the server log.
> Audit: `kv-tensor-split/RESULT_N9_TURBO3_AUDIT.md`.

## 2. No stacking collapse — the prediction failed

`TheTom/turboquant_plus/docs/papers/asymmetric-kv-compression.md` proposes **quantization
stacking**: KV error compounds *multiplicatively* with weight error in the attention logits,
and when both are lossy the result can exceed softmax's tolerance. Its catastrophic case was
**Q4_K_M weights + turbo3 KV → PPL 3,556** against a 6.58 baseline.

`AD-IQ2_S` carries **KLD 0.098** against Q4_K_M's ~0.011 in the same publisher's table —
roughly **9× lossier**. Stacking predicts this should be far worse. Greedy, temp 0, identical
prompt, 8k context:

| KV | result |
|---|---|
| f16 | reference |
| turbo4 | **byte-identical to f16** |
| turbo3 | **byte-identical to f16** |
| turbo2 | different wording, **arithmetic still correct** |

**Registered at 0.75 that a static low-bit weight + low-bit KV pairing would be badly degraded
or collapse. FALSIFIED at this context length.** turbo3 — the exact codec in the paper's
catastrophic pair — produced output indistinguishable from f16 on weights 9× lossier.

**Scope, stated plainly:** 8k context, 80-token generations, one prompt, greedy. This is not
perplexity over wikitext and not a hazard panel. The honest claim is **"the catastrophe does
not appear at short context"**, not "stacking is wrong". Depth is where KV error accumulates
and the test that matters (`U5h` on `.194`, plus a depth arm) is still pending.

## 3. The KV arithmetic transfers across machines and backends

Measured on the desktop at `-c 65536 -ctk turbo3 -ctv turbo3`:

```
ROCm0 | 16304 total = 15884 free + (11042 = 9692 model + 949 context + 400 compute)
```

| | |
|---|---|
| predicted from `.194`'s 64 KiB/token measurement | **896 MiB** |
| measured here | **949 MiB** |
| agreement | **within 6 %**, the gap consistent with the known fixed per-context overhead |

Different machine, different vendor (HIP vs CUDA), different weight quant (IQ2_S vs Q6_K) —
**the per-token KV cost is a property of the architecture and it carries.** That is what makes
the Step 1 measurement worth doing once per model rather than once per configuration.

## 4. ROCm's `hipMemGetInfo` does not report other processes' VRAM

> **ATTRIBUTION CORRECTED.** This section originally said *"llama.cpp's fit logic does not
> see the desktop's VRAM"*, implying a bug in `common_params_fit_impl`. **That is wrong.**
> `fit.cpp` calls `ggml_backend_dev_memory` → `cudaMemGetInfo` (hipified to `hipMemGetInfo`),
> which is the correct API. **llama.cpp asks properly and the ROCm driver answers wrongly.**
>
> Measured at the same instant, `-ngl 0` so the querying process held almost nothing:
>
> | source | free VRAM |
> |---|---:|
> | `hipMemGetInfo` | **16,036 MiB** |
> | sysfs `mem_info_vram_used` | **13,306 MiB** (2,997 used) |
>
> `hipMemGetInfo` accounted for **268 MiB of the 2,997 MiB actually allocated** — it reports
> roughly *total minus this process's own usage*, not system-wide free memory. The section
> below is retained; only the cause changes, and the practical consequence is identical.
> **Whether CUDA behaves the same is untested** — an attempt on `.73` with a concurrent
> VRAM holder was inconclusive because that build does not emit the breakdown line. Do not
> assume the finding generalises beyond ROCm.

The finding with the widest practical reach.

| source | free VRAM |
|---|---:|
| `mem_info_vram_used` (sysfs, ground truth) | **13,421 MiB** |
| **what `common_params_fit_impl` planned against** | **15,884 MiB** |
| **discrepancy** | **2,463 MiB** |

The desktop was holding **2,882 MiB**; llama.cpp accounted for only ~420 of it. Its own log
reads *"will leave 4841 >= 1024 MiB of free device memory, no changes needed"* — but measured
against real free memory that margin is **2,379 MiB**, roughly half what it believed.

**Consequence:** auto-fit on a display-driving card is optimistic by ~2.4 GiB on this system.
It survived here because the configuration was modest. Anyone trusting it to size context near
the limit will be handed a plan that OOMs — and the failure arrives at depth, long after load,
which is the worst time to discover it.

**Protocol implication:** Step 0's *"measure with your desktop running, then subtract another
GiB"* is not conservatism. **The tooling's own estimate is the thing being corrected.**

## What this does not establish

- **Not a fidelity result.** Byte-identical output on one prompt at 8k is a smoke test.
  `U5h` (low-bit TCQ ladder) and a depth arm remain the real measurements.
- **Not a 260k claim.** Nothing here ran past 65k.
- **TCQ untested here.** This HIP build carries `turbo2/3/4` only; `turbo2_tcq`, the codec the
  260k plan actually needs, exists only in buun's tree on `.194`.
- **One model, one quant, one prompt set.**

---

## 5. VBR runs on RDNA4 — and its auto-budget inherits the fit-logic error

**2026-08-18.** buun `02f8581` built for **gfx1201** (`build_rocm`, HIP), deliberately at the
**same commit as `.194`** so a later RDNA4-vs-Pascal comparison is not contaminated by two
weeks of upstream drift (the local tree had been sitting at `7939b6c4`, 2026-07-22).

**It arms and it works:**

```
VBR_VMM gate: dynamic=1 no_alloc=0 policy=0 is_turbo=1 n_stream=1 v_trans=0 -> wanted=1
VBR VMM pool #0: 2048.12 MiB VA reserved (device 0, 4 KiB pages), 0.12 MiB mapped up front
VBR degrade order: 160 baked steps (arch + KV-layout matched; n_layer 65 vs table 64)
VBR budget: 4737.22 MiB mapped-physical (degrade trigger armed)
```

`vbr-vmm.cu` calls the CUDA Driver VMM API (`cuMemCreate` / `cuMemSetAccess`); those hipify
cleanly and the pool allocates on ROCm. Output correct (`17 × 23 = 391`) at **29.5 t/s** —
marginally *faster* than the same model on f16 KV (28.6 t/s), so on this part VBR is not a
performance compromise. buun's baked pricing table matched the architecture despite the
`n_layer 65 vs 64` mismatch, logging it as an MTP/nextn-style variant rather than falling
through to the generic order.

**This answers a question worth answering: VBR is not CUDA-only in practice.**

### The connected finding: auto-budget is planning against phantom memory

The budget above was resolved **automatically** — *"KV budget auto (remaining VRAM, resolved by
fit)"*, landing on **4737 MiB**. But §4 of this receipt measured `common_params_fit_impl`
seeing **15,884 MiB free when sysfs reported 13,421** — it does not account for the desktop's
allocation.

**So auto-VBR on a display-driving card sizes its degrade schedule against ~2.4 GiB of memory
that does not exist.** The failure mode is specific and nasty: VBR's whole design is to *not*
degrade until it must, so an inflated budget means it holds a higher tier for longer and hits
real memory pressure **later and harder** — at depth, mid-conversation, rather than at load.

**This is now the strongest argument for pinning `VBR_BUDGET_MIB`, and it is not the one the
protocol originally gave.** Reproducibility was the stated reason. The better reason is that
**the automatic value is derived from a measurement that is wrong on exactly the hardware
class this protocol targets.** A pinned budget is not merely more comparable — on a desktop
card it is more *correct*.

Recommended for this machine: measure free VRAM from sysfs with the desktop running, subtract
1 GiB, subtract the model and compute buffers, and pin what remains. On the configuration
measured here that is roughly **2.0-2.2 GiB**, against the 4.7 GiB the tool chose for itself.
