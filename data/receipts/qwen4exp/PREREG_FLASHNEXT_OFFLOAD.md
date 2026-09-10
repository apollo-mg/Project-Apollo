# Pre-registration — can a 180B/6B-active model with an offloaded n-gram table beat a resident 27B?

**Registered 2026-08-27, before any weights were downloaded.** Model: `Qwen3.8-Flash-Next`
(`qwen4_exp`, 180B total). Target: `.194`, 4x Tesla P100 (64 GiB VRAM), 60 GiB RAM
(51 available), DDR4-2133, 1063 MHz / 150 W. Fork: `TheTom/llama-cpp-turboquant` PR #324
(imports upstream `ggml-org/llama.cpp#27742`) — **not yet merged, CI in flight**.

## Architecture, from `config.json` (not from the card's prose)

| | |
|---|---|
| experts | 512, **10 active/token**, `moe_intermediate_size` 640 |
| expert params | 48 x 512 x (3 x 2560 x 640) ~ **121B** |
| n-gram table | `ngram_size` 3, `ngram_vocab_size_base` **20,000,000**, `ple_embed_dim` 2560 ~ **51B** |
| attention | 24 heads, **2 KV heads**, `full_attention_interval` **4** |
| other layers | linear attention + SSM (`mamba_ssm_dtype` float32), constant-size state |
| MTP | hybrid, 1 layer — speculative decoding is built in |

## The mechanism under test

The n-gram table is a **lookup**: only rows for trigrams present in context are read — a few KB
per token, latency-bound. MoE experts are **streamed**: 10 of 512 change every token, ~1.2 GB
per token at IQ4. Those have opposite offload characteristics, which is what the card means by
"more amenable to offloading than MoE".

**Therefore the placement that should win:** n-gram/PLE tensors on CPU (~27 GiB in RAM),
experts + attention resident on the P100s (~64 GiB). Naive layer-wise offload should be
markedly worse, because it spills experts.

## Predictions (scored honestly, including the ones that fail)

| # | prediction | confidence |
|---|---|---|
| P1 | Flash-Next IQ4_XS with n-gram-on-CPU **exceeds 13.8 tok/s**, the measured 27B-Q6_K-on-2xP100 baseline | 0.60 |
| P2 | **Placement matters more than offload fraction**: n-gram-on-CPU beats naive `-ngl`-style layer offload of the same byte volume by **>2x** | 0.75 |
| P3 | KV at 32k is **< 1.5 GiB** at f16 — smaller than the 1,824 MiB measured for 27B dense at ~29k | 0.70 |
| P4 | It runs **at all** on sm_60 without new kernels (PR touches **zero** `ggml-cuda`/`ggml-hip` files) | 0.55 |
| P5 | Prompt processing is **not** competitive — prefill touches many more n-gram rows than decode | 0.65 |

**P4 is the load-bearing risk.** No backend files changed means op coverage is inherited; a
hybrid SSM + linear-attention path that nobody has exercised on Pascal is where this most
plausibly falls over. A failure there ends the test before P1 is measurable.

## What would falsify the interesting result

If n-gram-on-CPU and naive offload perform the same, the "more amenable to offloading" claim is
not doing work at this scale, and the win (if any) is just sparse activation.

## Envelope

One model, one quant (IQ4_XS), one node, one architecture family, Pascal only. Clock/power
recorded per campaign discipline. **Baseline for comparison is 13.8 tok/s** (`Qwen3.8-27B-UD-IQ4_XS`
F16-KV arm, 2x P100, `RESULT_VBR_FIDELITY.md`) — note that is 2 GPUs vs 4 here, so the
comparison is "what this box can serve", not a controlled per-GPU figure.
