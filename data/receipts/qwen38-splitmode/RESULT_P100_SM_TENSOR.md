# `-sm tensor` is 1.63x faster than `-sm layer` on 2x P100 — and layer split is worth nothing

**Date:** 2026-08-14 · **Node:** `.73`, 2x Tesla P100-PCIE-16GB (sm_60), **150 W / 405 MHz
idle at sample time** (standing fleet config since 2026-07-17) · **Interconnect: PHB, no
NVLink** — both cards reach each other through the host bridge over PCIe, P2P DMA available
**Build:** `buun_vbr` (buun-llama-cpp) · **Model:** `Qwen3.8-27B-UD-IQ3_XXS`, 11.09 GiB,
dense, 66 blocks · `-ngl 999 -c 8192 -fa on -np 1`, temp 0 / top_k 1 / seed 1234

## Result

Four arms, **A/B/B/A ordering**, 5 prompts x 2 reps each, plus a single-GPU baseline added
afterwards:

| arm | median t/s | mean |
|---|---|---|
| A `-sm layer -ts 1,1` | 8.59 | 8.57 |
| B `-sm tensor` | **13.93** | 13.92 |
| C `-sm tensor` (repeat) | **13.93** | 13.92 |
| D `-sm layer -ts 1,1` (repeat) | 8.52 | 8.48 |
| E single GPU, no split | 8.59 | 8.58 |
| F single GPU (fresh load) | 8.58 | 8.56 |

**Tensor split is 1.63x faster than layer split — and 1.62x faster than a single card,
which is the comparison that actually matters.**

## The arm that decides what this means: one GPU, no split

This model is 11.09 GiB and the layer-split arm used ~6 GiB per card, so it **fits on a
single P100** (12033 MiB resident, second card empty). Without this cell the result is
unreadable — 1.63x could mean tensor split is a real gain, or that layer split is a
self-inflicted loss you avoid by simply not splitting.

Pooled across both reps of each mode, n=20 samples per mode:

| arm | median t/s | mean | vs single GPU |
|---|---|---|---|
| **single GPU, no split** | **8.585** | 8.572 | — |
| `-sm layer -ts 1,1` | 8.540 | 8.524 | **0.995x** |
| `-sm tensor` | **13.930** | 13.921 | **1.623x** |

**Layer split across two P100s is 0.5 % slower than using one P100.** It buys nothing.

And it is inert, not merely slow: the layer-split arm is **bit-identical to the single-GPU
arm** — same visible text and the same `completion_tokens` on all 10 paired samples.
Pipelining relocates layers to a second device without changing the computation at all on a
single sequence. The second card holds 6.6 GiB of weights and contributes no throughput.
Tensor split, by contrast, differs from single-GPU on both `reason` and `repeat`.

So the headline is not "tensor beats layer". It is **tensor is the only one of the two that
converts a second GPU into anything** — 1.623x over one card, 81.1 % scaling efficiency.

## Engagement: four independent proofs, none of them the timing

The A/B log alone cannot prove `-sm tensor` engaged — every arm overwrote a single
`srv_sm.log`, and this build prints no split-mode line at default verbosity. Inferring
engagement from the speedup is the exact reasoning that produced the Vulkan MoE-cache
retraction in `rdna4-moe-cache/RESULT_HIP_VULKAN.md`. So it was established four other ways.

**1. The loader says so.** Relaunched at `-lv 5`, which exposes the `load_tensors` block:

| arm | `load_tensors: layer N assigned to device ...` |
|---|---|
| `-sm layer -ts 1,1` | layers 0-32 -> `CUDA0`, layers 33-65 -> `CUDA1` |
| `-sm tensor` | **every layer -> `Meta()`** |

(66 blocks, 0-65, split 33/33. Each assignment is logged twice — a planning pass and the
allocation — so the raw line counts are 66/66 and 132.)

`Meta()` is the marker `llama-model.cpp:322` tests (`devices[0].is_meta`) before throwing
`LLAMA_SPLIT_MODE_TENSOR not implemented for architecture` on a denylisted arch. The loader
itself reports tensor-parallel placement.

**2. Per-device VRAM is byte-identical under tensor split.**

| arm | GPU0 | GPU1 | delta |
|---|---|---|---|
| `-sm layer -ts 1,1` | 5933 MiB | 6647 MiB | **714 MiB** |
| `-sm tensor` | 6243 MiB | 6243 MiB | **0 MiB** |

Layer split lands on a layer boundary — 33 layers each by count, but 714 MiB apart in bytes,
because an unsloth dynamic recipe does not give every layer the same type. Tensor split
splits each tensor, so the two buffers come back equal. **A silently-ignored flag cannot
produce that.**

**3. Utilisation shows pipelining vs parallelism directly.** 60 samples at 0.3 s during
steady-state decode:

| arm | GPU0 | GPU1 | **sum** | both >50 % |
|---|---|---|---|---|
| `-sm layer` | 47.0 % | 52.3 % | **99.2 %** | 4/60 |
| `-sm tensor` | 92.4 % | 92.2 % | **184.6 %** | 57/57 |

buun_vbr documents layer as *"split layers and KV across GPUs (pipelined)"* against tensor's
*"(parallelized)"*. Under a pipelined split on one sequence only one card computes at a time,
and the two cards together deliver **one card's duty cycle** — 99.2 %. That sum is the robust
part of this measurement: `utilization.gpu` is a time-averaged busy fraction, so the tensor
arm's *magnitude* partly reflects its own higher throughput, but the layer arm summing to
~100 % does not depend on rate.

**4. Output diverges at temp 0**, partially — consistent with a reduction-order change:

| prompt | visible output | tokens (layer / tensor) |
|---|---|---|
| `prose` | **byte-identical**, 1508 chars | 320 / 320 |
| `reason` | **differs from char 0**, 244 vs 318 chars | 248 / **257** |
| `repeat` | identical, 170 chars | 219 / **221** — diverges in the think channel |
| `code`, `list` | 0-1 chars — cap-death inside the think block, **comparison vacuous** |

Most greedy decodes agree and some do not, which is the expected shape: `FA_EQUIVALENCE_SM60`
measured same-top **98.686 %** on this hardware from a mere `-fa` flag. Tensor split changes
what order partial sums are reduced in; it is not a correctness break, but **reproducers
should expect different text from the same seed.**

The single-GPU arm supplies the **negative control** this needs. Layer split is bit-identical
to one GPU across all 10 paired samples, so the harness is deterministic at temp 0 and the
divergence under tensor split is not run-to-run noise — it appears when, and only when, the
reduction order changes.

## Reproducibility is the strongest this fleet has recorded

`smtensor_1` and `smtensor_2` are identical to **0.01 t/s on all five prompts** across a
full server restart. `smlayer_1` 8.59 vs `smlayer_2` 8.52, with one outlier (`reason` rep0,
7.87). This matters because this fleet has repeatedly produced **2-3.9x position artifacts
on identical configs** (`rdna4-moe-cache/RESULT_DEEPSEEK_V4_P100.md`), and
`agent-benchmark-determinism` records temp-0 runs on this exact node as non-reproducible at
the task level. Throughput, unlike task accuracy, reproduces here.

## Architecture gate: this is a denylist, and forks disagree

`llm_arch_supports_sm_tensor()` in `llama-arch.cpp:995` is a **denylist with
`default: return true`** — 25 architectures return false, everything else is permitted:

```
GROK MPT PLAMO2 MINICPM3 GEMMA3N MAMBA MAMBA2 JAMBA FALCON_H1 OLMO2 OLMOE
DEEPSEEK2 DEEPSEEK32 DEEPSEEK4 GLM_DSA BITNET T5 NEMOTRON_H NEMOTRON_H_MOE
GRANITE_HYBRID LFM2 LFM2MOE MINIMAX_M2 MISTRAL4 KIMI_LINEAR
```

Qwen 3.8 is not on it, which is why this test could run at all. **`DEEPSEEK4` is** — so the
DeepSeek V4 `-sm tensor` comparison cannot run on this node; it throws at model construction.
On `.194` (giveen tree) DeepSeek V4 *is* permitted. Two forks, same flag, different answer.
Anyone benchmarking `-sm tensor` across builds is comparing gates, not hardware.

## Practical reading

For a model that fits on one card, on this hardware:

- **`-sm layer` across 2 GPUs is not a performance feature.** It exists to fit models that do
  not fit. On a single sequence it produces bit-identical output at 0.995x the speed of one
  card, while occupying two. If you have been running a fitting model on `-sm layer` and
  reading the second GPU's VRAM as evidence it is helping, it is not.
- **`-sm tensor` is the setting that converts a second GPU into speed** — 1.62x over one card
  here, 81 % scaling, without NVLink, on 2016 silicon over PHB.
- The flag is **architecture-gated and fork-dependent**. Check the denylist in the build you
  are actually running before reading a null result as a hardware result.
- **Batching is the untested alternative.** `-np 1` is the worst case for pipelining: with
  concurrent sequences a layer split can keep both cards busy on different micro-batches, and
  the 0.995x here would not hold. This receipt measures single-stream latency, which is the
  interactive-agent case this fleet runs, not throughput under load.

## Limits

- **One model, one quant, one context length, one node, 2 cards.** Nothing here predicts
  scaling to 4 cards (`.194`) or to MoE, where expert routing interacts with tensor split in
  ways this dense model cannot show.
- **`-np 1` only.** See the batching note above — this is the single-stream case, and it is
  the case most favourable to tensor split.
- `-r 2`, 5 prompts. K is small — but the arms reproduce to 0.01 t/s, which is the relevant
  precision.
- **Throughput only. No quality measurement**, and outputs are known to differ between modes.
- Prompt processing is not separated from generation; these are end-to-end completion rates
  at 320 `n_predict`.
- Utilisation sampling is `nvidia-smi` polling, a time-averaged busy fraction, not an
  occupancy or simultaneity instrument. It is reported as corroboration, not as the proof.
- The `code` and `list` prompts cap-died inside the think block at 320 tokens, so those two
  contribute throughput but no usable text comparison.
- **Harness note:** `mtp_ab.py` originally read only `content` and was blind to
  `reasoning_content` — the same defect found in `qwen38-lowbit/run_2x2.py`. Throughput was
  never affected (`completion_tokens` counts both fields, so every t/s number here predates
  and survives the fix), but the first text comparison reported `code` as "identical" when
  both arms had empty visible output. Patched before the single-GPU arm, which is why those
  logs carry `c=` and `rc=` lengths and the earlier ones do not. **The `qwen38-mtp` receipts
  were produced with the unpatched harness** — their throughput stands, any text claim in
  them does not.
