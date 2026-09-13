# Note — who owns Flash-Next support now. Our 09-02 "no overlap" read is obsolete.

**2026-09-13, source review only.** `.194` is off and `.73` is running the EXL3 compression test, so
nothing here was built or run. Method: fetched `spiritbuun/buun-llama-cpp` and read `origin/master`;
read PRs #324 and #362 on `TheTom/llama-cpp-turboquant`.

## The correction

`RESULT_BUUN_MASTER_COMPARISON.md` (2026-09-02) concluded buun and the #324 effort were **"different
axes, no overlap"** — buun on single-GPU throughput, #324 on multi-GPU `-sm tensor`. **That is no longer
true.** Between 09-06 and 09-10 buun moved onto the multi-GPU axis and closed both gaps that receipt
recorded as absent in his tree:

| our 09-02 finding | buun's master today |
|---|---|
| `GGML_OP_LIGHTNING_INDEXER` dispatch **ABSENT** | **present**, `ggml/src/ggml-backend-meta.cpp:1132` |
| `memset_tensor` = `nullptr, // TODO implement` | **implemented**, `ggml_backend_meta_buffer_memset_tensor` (:1426, wired at :1885) |

Plus, in the same window: tensor-split rules for native group-scale grids and fused qkv(z)
(`edc55804a`), FLA gated-delta-net prefill on a device's head subset (`746c4a726`), per-device whole
compute step captured into one CUDA graph (`d73565895`), MoE cache for Qwen4 tensor split (`29c27a54e`),
server cache state bound to physical devices (`a56eeef51`), and `9edf91e99` re-admitting Qwen4 to
`-sm tensor` after a master sync re-imported upstream's deny list.

**`d73565895` does nothing for this fleet:** CUDA graphs are disabled below Volta
([[pascal-never-uses-cuda-graphs]]), so sm_60 only ever runs the fallback path.

## The three-tree map

| tree | owns | Flash-Next content |
|---|---|---|
| **upstream ggml-org** | the architecture | `6c84c7d5d` adds `qwen4exp` (#27742); `6fe749801` reduces graph splits (#27880); **`#27941` deny-lists `-sm tensor` for `qwen4exp`** over NaN logits |
| **TheTom/llama-cpp-turboquant** | multi-GPU via the **meta backend** | **#324 merged 08-31** (author giveen, port of #27742) — split states, DS4 patterns, `memset`, `LIGHTNING_INDEXER`; Mark's undersubscribed-split finding fixed centrally by Tom in `3042c600b`. **#362 open** (jasstrong): four Flash-Next fixes |
| **spiritbuun/buun-llama-cpp** | everything above **plus ingestion and EXL3** | the multi-GPU work listed above, safetensors ingestion, MTP sidecars, and EXL3 for Qwen4 |

**Why #362 sits in Tom's fork rather than upstream:** by Jas's own assessment patches 1, 2 and 4 are
upstream-appropriate, but they cannot meet ggml-org's AI-assistance contribution requirements (BACKLOG
O10). That is a policy routing decision, not a technical one, and it is why Flash-Next fixes are
scattered across three trees.

## The item with the largest stake for this fleet

**`8488d453e` — "EXL3 for Qwen4 (Qwen3.8-Flash-Next): experts, indexer, n-gram table"** adds
`GGML_TYPE_EXL3N_2 .. EXL3N_8` (`ggml/include/ggml.h:488-494`): dedicated EXL3 n-gram row types at
**2–8 bits**, 160-wide rows, fp16 row scale, K-bit tail-biting chunks, with a CPU decoder stated to be
bit-exact against exllamav3's `dequant_rows`.

**This targets exactly the tensor our bottleneck runs through.** `per_layer_token_embd.weight` is one
**26.82 GiB** tensor in our IQ4_XS quant, and `d528c300c` states the design constraint plainly: *"The
PLE table is gathered on the CPU."*

**So EXL3N does not move the table to VRAM — it shrinks what each gather reads from host RAM.** The
files it touches are `ggml-cpu/ops.cpp`, `ggml-quants.c`, `ggml.c`, `ggml-common.h`,
`llama-safetensors-qwen4exp.cpp` — **no `ggml-cuda` file**, consistent with a CPU-side gather.

**The trade, stated as a question rather than a claim:** at ~3 bits against a BF16 table the bytes per
gather fall roughly 5×, which lands on the resource `RESULT_FLASHNEXT_PREFILL.md` measured as saturated
(prefill flat at ~35 tok/s across a 7× prompt range). The cost is trellis decode on the CPU — on `.194`
that is 2× Haswell-EP with **no AVX-512**. Whether it nets out is empirical and unmeasured, and it is
the thing most worth measuring before buying DIMMs, because it competes for the same win.

**Also relevant to the EXL3 campaign:** `32c2c1479` — *"model: reject unsupported multi-device EXL3
tensor splitting"*. EXL3 stays on `-sm layer` across devices, which is what test 10 is already doing.

## Not established here

- **Nothing was built or run.** Every statement above is a source read; no claim is made that any of it
  works on sm_60, and `EXL3N` has no CUDA path to work *on* a GPU by design.
- **No Flash-Next EXL3 conversion is known to exist on disk.** The importer reads safetensors, so this
  needs the original checkpoint and a conversion — the exllamav3 path already open as campaign O8.
- **The NaN question behind upstream's deny list is still unresolved**, and buun's re-admission does not
  resolve it: the generic CPU-vs-device arm still compares `if (nmse_val > 1e-4)`, which `nan` passes
  ([[tensor-split-denylist]]).

---

## Correction — 2026-09-13 ~12:10, same day

Two errors in *"The item with the largest stake for this fleet"* above. Found when Mark raised EXL3 for
Flash-Next on `.194` and I re-read `RESULT_FLASHNEXT_PREFILL.md` against this note.

1. **Wrong resource.** I wrote that EXL3N "lands on the resource `RESULT_FLASHNEXT_PREFILL.md` measured
   as saturated." That receipt attributes the flat ~35 tok/s prefill to **streaming offloaded
   experts** from host RAM — ~1,800 prompt tokens touch essentially every expert. The PLE table is read
   by **sparse gather**, one row per token per layer, and that sparsity is the architecture's whole
   pitch. Cutting bytes per gather barely moves total host traffic. **EXL3N is a host-RAM *capacity*
   feature**, which is exactly how `d528c300c` frames the problem it solves: a BF16→F32 conversion
   doubling resident RAM and pushing decode into paging.
2. **Wrong baseline.** "Roughly 5× fewer bytes" compared 3-bit EXL3N against a **BF16** table. Ours is
   not BF16: 26.82 GiB against buun's ~100 GB BF16 figure is **roughly 4.5 bits per element** already.
   Against that, 3-bit EXL3N is about a third smaller, not 5×.

**Retracted in consequence:** EXL3N does **not** "compete for the same win" as filling `.194`'s memory
channels. **What does is EXL3 on the experts.** If they become fully VRAM-resident, expert streaming
stops and host bandwidth largely stops mattering for this model — so for Flash-Next throughput, EXL3
residency and more DIMMs are **substitutes, not complements**. DIMMs still carry DS4, whose experts sit
on the CPU by design (`-ncmoe 40`), and capacity in general.
