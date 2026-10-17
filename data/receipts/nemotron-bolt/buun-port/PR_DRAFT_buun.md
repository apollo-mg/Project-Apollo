<!-- Posted 2026-10-17 as https://github.com/spiritbuun/buun-llama-cpp/pull/146 (commit f5f1f10e9 on apollo-mg:nemotron35-runtime), Mark-approved. -->
# Title
model : Nemotron 3.5 runtime support (per-layer expert counts, MTP-layer scales) from upstream #30520

# Body
## What

Cherry-picks the runtime part of ggml-org/llama.cpp#30520 (merged upstream as `cd0a5b6a1`, author frozenblade1224):
one file, `src/models/nemotron-h.cpp`, +19/-5. With it, buun loads NVIDIA's Nemotron 3.5 Bolt 74B-A9B and Super VL
120B-A12B text models.

- **Per-layer expert counts.** Bolt was compressed from Super VL with a router-guided search that keeps a different
  number of routed experts in each MoE layer. Each layer's count is now read from its router tensor
  (`ffn_gate_inp`, `ne[1]`) instead of the global `n_expert`, and validated against `n_expert_used` and `n_expert`.
- **MTP-layer scales.** The MTP layers load their expert and shared-expert `scale` / `input_scale` tensors (optional),
  as the trunk layers already do.

**Not included:**
- the LiliCorr / DFlash changes from the same PR (`common/speculative.cpp`, `src/models/dflash.cpp`), since buun's speculative
  code is far from upstream's and those hunks don't apply;
- the mtmd (vision) part, which I haven't tested.

So this is text-only, with no LiliCorr drafting.

## Testing (4x Tesla P100, sm_60, CUDA 12.4)

Bolt 74B-A9B, AtomicChat `AD-Q8_0` (built from NVIDIA's BF16), on this commit and on upstream master `620d222`.
Both had identical flags and placement (`-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off`, routed experts of
the last 12 MoE layers on CPU, `-ts 21,14,14,40`) and a fresh server each:

| | upstream `620d222` | buun `34ef0ef7c` + this commit |
|---|---|---|
| loads (heterogeneous expert counts) | yes | yes |
| VRAM after load (MiB) | 14371 / 14135 / 13507 / 13807 | identical |
| decode, prose / code / JSON, 256 tokens | 15.1-15.2 tok/s | 14.8 tok/s |
| server errors | 0 | 0 |
| 60-question factual set (greedy, graded), same grade as upstream | | 58 / 60 (50 byte-identical answers) |

The two differing answers are hard questions near the boundary. With different kernels underneath, that looks like ordinary
numeric-path noise, not a port problem.

## Two things I hit along the way (not changed by this PR)

1. **buun master doesn't build with CUDA 12.4 + gcc 13.4.** `ggml-cuda/moe-cpu-share.cu` (since 10-06) ends up including
   GCC 13's `amxtileintrin.h`, and nvcc 12.4 stops on `identifier "__builtin_ia32_ldtilecfg" is undefined`. I built with
   `-DCMAKE_CUDA_FLAGS=-D_AMXTILEINTRIN_H_INCLUDED` (the header guard pre-defined for CUDA compiles only; no CUDA file uses
   AMX). I mentioned this on Discord.
2. **Headroom.** With the last 8 MoE layers spilled (~250-450 MB free per card), upstream ran but buun returned a 500 on
   its first request: `CUDA pool[3]: growing 206.00 MiB to 290.00 MiB failed`. Static allocation was identical, but buun's
   pool wanted a little more on the last card. At 12 spilled layers both ran cleanly.

Full receipt, logs and the 60-question script:
https://github.com/apollo-mg/Project-Apollo/blob/main/data/receipts/nemotron-bolt/buun-port/RESULT_BUUN_PORT.md

*Posted by my agent (Claude Opus 5.5) on my behalf. The hardware and the runs are mine; I reviewed this before it went out.*
