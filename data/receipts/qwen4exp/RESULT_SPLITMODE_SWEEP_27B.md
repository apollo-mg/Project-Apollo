# Result — layer split is inert at every device count, and tensor split **peaks at three cards**

**Run 2026-09-14 09:27–09:32 on `.194`** (4× P100 sm_60, 150 W / 1063 MHz), buun **`c7f114d34`**,
`GGML_CUDA_ALLREDUCE=internal`. Qwen3.8-27B **UD-IQ3_XXS** (11.9 GB — fits on a single P100, so device
count is the only variable across all seven arms). `-ngl 99 -c 2048 -np 1 -fa on -ctk f16 -ctv f16 -fit off`.
Three reps of 128 tokens at `ignore_eos`, median of the server's own `predicted_per_second`.

Prompted by buun: *"a lot more work was put into -sm tensor during the safetensors work"*, and by Mark's
*"should probably re-test speeds on 27B too."* **Coherence is checked before the timing on every arm** —
a speed number from a numerically broken arm is meaningless, which is exactly what `c232282aa`'s 6.14 tok/s
was. **All seven arms coherent.**

## The sweep

| arm | `-sm` | cards | decode tok/s | vs 1 card | parallel efficiency | rep spread |
|---|---|---|---|---|---|---|
| S-1dev | layer | 1 | **9.21** | 1.00× | — | 0.11% |
| L-2dev | layer | 2 | 9.21 | **1.00×** | 50% | 0.11% |
| L-3dev | layer | 3 | 9.19 | **1.00×** | 33% | 0.00% |
| L-4dev | layer | 4 | 9.20 | **1.00×** | 25% | 0.11% |
| T-2dev | tensor | 2 | 14.91 | 1.62× | 81% | 0.07% |
| **T-3dev** | tensor | 3 | **17.13** | **1.86×** | 62% | 0.18% |
| T-4dev | tensor | 4 | 15.60 | 1.69× | 42% | **2.18%** |

## 1. Layer split is inert — confirmed across a 4× hardware spread

**9.21 / 9.21 / 9.19 / 9.20 at one, two, three and four cards.** The VRAM tables show the model genuinely
distributed (11,449 on one card; 3169/3009/3169/3527 on four), so the extra cards hold weights and
contribute *nothing* to single-request throughput. Layer split is sequential pipelining: one GPU computes
while the rest wait.

**This reproduces the 2026-08-14 finding** (`qwen38-splitmode/RESULT_P100_SM_TENSOR.md`, "layer split across
two is inert and bit-identical to single") **to two decimal places on a build a month newer.**

**Layer split buys capacity, never speed.** State it that way; "tensor is 1.6× faster than layer" invites the
reading that layer split does something.

## 2. Tensor split peaks at three cards — the fourth costs 9%

**17.13 tok/s at three cards against 15.60 at four.** Three cards is strictly better on both axes: faster
**and** it leaves a card free for other work. **For serving this model on `.194`, use three.**

Parallel efficiency falls 81% → 62% → 42%. The marginal return collapses: the second card adds **+5.70**
tok/s, the third **+2.22**, the fourth **−1.53**.

**The noise corroborates the mechanism.** T-4dev's rep spread is **2.18%** where every other arm sits at or
below 0.18% — 12× noisier. GPUs 0–1 and 2–3 sit on separate root complexes (`GPU0<->GPU1 PHB`,
`GPU2<->GPU3 PHB`, cross-domain `SYS`; `RESULT_d929da17b_VERIFY.md`), and the four-way all-reduce is the only
configuration paying that cross-socket link on every one of 48 layers.

## 3. The dense/MoE inversion is about the model, not the device count

Measured on the same box, same build, **same four devices**:

| model | `-sm layer` | `-sm tensor` | winner |
|---|---|---|---|
| Qwen3.8-27B (dense) | 9.20 | **15.60** | tensor, 1.70× |
| Flash-Next UD-Q2_K_XL (sparse MoE) | **17.59** | 12.30 | **layer, 1.43×** |

**Opposite directions under identical conditions**, which rules out device count as the cause and confirms
the inversion is architectural.

**Mechanism, consistent with both rows but not isolated by measurement:** tensor split pays an all-reduce per
layer and repays it with parallelized compute. A dense layer has full-width matmuls to parallelize, so the
trade is profitable to three cards. A Flash-Next layer activates **10 of 512 experts** — very little compute
against the same communication — so the all-reduce dominates and layer split wins outright. Flash-Next decode
was independently found overhead-bound in Stage 3, which points the same way.

## Limits

- **One quant, one prompt, one context length.** IQ3_XXS at a short prompt, `-c 2048`. Not a long-context
  result, and the absolute numbers are lower than the daily driver's Q6_K.
- **Not comparable to the `.73` figures** (Q6_K layer 7.81 → tensor 13.22; EXL3 4.00bpw 6.96 → 11.26, both
  on two P100s at `9ae8f0f40`). Different node, quant and build. **The comparable quantity is the ratio**,
  and 2-card tensor lands at **1.62×** here — the same ratio as 08-14 and as the 09-12 EXL3 run.
- **Flash-Next has no single-card baseline** and cannot have one (~50 GB), so its parallel efficiency is
  undefined; only the layer-vs-tensor comparison at four cards is available for it.
- **No `-ts` tuning.** Every arm used the default split.

Artifacts: `tsplit/sweep27b/` — `rows.jsonl`, `sweep.log`, `sweep27b.sh`.
