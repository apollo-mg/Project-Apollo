# Predictions — qwen4exp `-sm tensor` patch

Logged **2026-08-28, before the patched build finished**. Patch: add `LLM_ARCH_QWEN4EXP` to
the two Qwen-GDN-family arch gates in `llama_meta_device_get_split_state`
(`llama-model.cpp:533` segments, `:646` granularity). Inner `if (arch == LLM_ARCH_QWEN3NEXT)`
at `:544` deliberately untouched, so qwen4exp falls to the **else** (Qwen 3.5, tiled) branch.

Target: `.194`, 4x P100-16GB sm_60, `Qwen3.8-Flash-Next-UD-Q2_K_XL`, `-ngl 99 -sm tensor`,
`GGML_CUDA_ALLREDUCE=internal`, 150W/1063MHz clock cap.

| # | Prediction | Conf |
|---|---|---|
| P1 | Patched build loads without aborting in `llama_meta_device_get_split_state` | **75%** |
| P2 | Given P1, generation is coherent (tiled broadcast is the correct choice) | **85%** |
| P3 | Expert gate/up + down (`n_ff_exp` 640, granularity 128) split **128/128/128/256** | **75%** |
| P4 | Dense `attn_q` (12288, granularity 6144) splits **0/6144/0/6144** — 2 of 4 cards | **75%** |
| P5 | The 36 linear layers split **perfectly evenly** (512/512/512/512 on qkv) | **80%** |
| P6 | Decode throughput beats the 15-16 tok/s layer-split floor | **60%** |
| P7 | `test-llama-archs` now passes qwen4exp (was the only arch of ~30 failing) | **80%** |

## Why P6 is only 60%

The receipt's "1.5-3x headroom" estimate was made before I had the granularity numbers. Two
things now cut against it and one cuts for it:

- **Against:** tensor parallelism all-reduces per layer; 48 layers x crossing the inter-socket
  `SYS` hop (GPU0/1 on NUMA 0, GPU2/3 on NUMA 1). P100s have no NVLink on this board.
- **Against:** dense attention lands on 2 of 4 cards (P4), so 12 of 48 layers are half-parallel.
- **For:** 36 of 48 layers are linear-attention and split perfectly evenly (P5), and the MoE
  expert weights — the 858 MiB/token that actually dominates decode traffic — split ~4 ways
  across every layer.

Honest position: I expect a gain, but the all-reduce cost on a two-NUMA-domain box with no
peer link could plausibly eat all of it. A *slowdown* would not falsify the patch, only the
headroom estimate.

## Correction to my own arithmetic

I first computed expert gate/up granularity as 256 (from `ffn_gate_exps` being IQ2_XS,
block 256) and predicted a 0/256/0/384 split that would leave two cards with no expert
weight at all. That was wrong: `get_split_granularity` takes `blck_size` from
`tc.tensor_axis_0->type`, and for gate/up the axis-0 tensor is **`ffn_down_exps.weight`**
(IQ4_NL, block **32**), giving `lcm(32,128) = 128`. Hence P3's 128/128/128/256.
