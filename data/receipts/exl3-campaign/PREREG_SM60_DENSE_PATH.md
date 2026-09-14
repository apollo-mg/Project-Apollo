# Prereg — what the dense-GGUF fallback actually costs on sm_60 (baseline for an HGEMM-56 attempt)

**Written 2026-09-14 ~16:30, before any arm runs.** For an80sPWNstar's sm_60 kernel thread. Mark's go.

## Why

`RESULT_EXL3_SM60_INFERENCE.md` established from source that **`ggml_cuda_should_use_mmq` returns
`cc >= GGML_CUDA_CC_PASCAL && n_experts > 0`** when the highest compiled arch is below
`GGML_CUDA_CC_DP4A` (610). GP100 is 600, so **MMQ is MoE-only on P100 and dense models never reach it** —
every batched matmul dequantises to fp16 and calls cuBLAS. That receipt states plainly:

> *(The gate is read from source; the buffer sizing is inferred from the code path, not measured.)*

**This test measures it.** A packed-half2 kernel (the HGEMM-56 proposal) targets exactly this path, and it
currently has a diagram but no number to beat.

## The measurable signature

If dense GGUF dequantises per batch, **peak VRAM must grow with `-ub`**, because the fp16 working set is
proportional to the micro-batch. If MMQ were running, it would not. EXL3 bounds the same step at 256 MB
chunks (`exl3.cu`), so it is the natural control: **its peak VRAM should be flat in `-ub`.**

## Setup

- **`.194`, two P100s** (`CUDA_VISIBLE_DEVICES=0,1`) to match the node shape the original OOM was seen on,
  `GGML_CUDA_ALLREDUCE=internal`, buun `c7f114d34`, `-sm layer -fit off -ngl 99`, f16 KV.
- **Dense arm:** Qwen3.8-27B **Q6_K** (22.9 GB) — the model that OOM'd.
- **Control arm:** Qwen3.8-27B **EXL3 3.00bpw**, same flags.
- **Sweep `-ub` ∈ {8, 64, 128, 256, 512}**, one server per setting, prefill a fixed 2,048-token prompt.
- **Recorded per arm:** peak VRAM (summed across both cards), prefill tok/s, and whether it loaded at all.
- **An arm that OOMs is a result, not a failure** — the `-ub` at which Q6_K stops fitting is the number
  that made `-ts 3,2` necessary.

## Predictions

| id | prediction | confidence |
|---|---|---|
| P-H1 | **Q6_K peak VRAM grows monotonically with `-ub`** — the dequant-pool signature | 85% |
| P-H2 | **EXL3 peak VRAM is flat in `-ub`** (within 500 MiB across the sweep) — bounded chunks | 80% |
| P-H3 | **Q6_K fails to load or OOMs at some `-ub` ≤ 512** on two cards | 60% |
| P-H4 | **Q6_K prefill tok/s improves with `-ub` up to at least 128** before flattening | 70% |

**P-H1 and P-H2 together are the evidence** that dense takes the dequant path and EXL3 does not. Either
failing means the source reading is wrong or something else dominates, and the HGEMM-56 premise needs
re-examining before anyone writes a kernel.

## Declared in advance

- **This measures the fallback, it does not prove MMQ is absent.** A direct proof needs a profiler or a
  `GGML_CUDA_FORCE_MMQ` build; neither is run here. The claim scored is about *memory behaviour consistent
  with dequantisation*, not about which kernel launched.
- **Not a speed comparison between EXL3 and GGUF.** Different formats, different bit rates. EXL3 is the
  control for *memory scaling*, nothing else.
- **One model, one prompt length, two cards.** Prefill only; decode is a different path and not measured.
- Peak VRAM is `nvidia-smi` sampled at 2 s, so it under-reports brief spikes. Stated, not corrected for.

**Deliverable:** a table an HGEMM-56 attempt can be measured against — current prefill throughput, and the
memory the dequant path costs at each `-ub`.
