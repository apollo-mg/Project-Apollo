# Port check -- Nemotron 3.5 runtime support cherry-picked into buun: Bolt loads and answers like upstream; buun is 2.6 % slower here

**Date:** 2026-10-16 evening. An engineering check before offering buun a PR (buun on Discord: "sure, would love that").

**The patch:** `src/models/nemotron-h.cpp` only, from upstream merge `cd0a5b6a180dff0048e5fd993098b21c0b2c91b8`
(ggml-org/llama.cpp#30520, author frozenblade1224): per-layer routed-expert counts read from each layer's router tensor
(Bolt's compression gives layers different expert counts) and scale tensors for the MTP layers. Applied cleanly to buun
head `34ef0ef7c`; commit `09e85b564` on .194 (`nemotron35-runtime.patch` here). The LiliCorr/DFlash parts of that PR
do not apply (buun's speculative code differs by thousands of lines) and the mtmd (vision) part was not attempted.

**Build note (not the patch):** buun head does not compile with the fleet's CUDA 12.4.131 + gcc 13.4: its
`ggml-cuda/moe-cpu-share.cu` (since 2026-10-06) pulls GCC 13's `amxtileintrin.h` into a CUDA translation unit and
nvcc 12.4 fails on `__builtin_ia32_ldtilecfg`. Built with `-DCMAKE_CUDA_FLAGS=-D_AMXTILEINTRIN_H_INCLUDED` (header
guard pre-defined for CUDA compiles only; no CUDA file uses AMX). Reported to buun (Mark, Discord, 21:50).

**Test:** Bolt 74B-A9B AtomicChat AD-Q8_0 (sha256 verified), .194 4x P100 150 W / 1063 MHz, both builds with identical
flags: `-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off`, routed experts of the last 12 MoE layers on CPU,
`-ts 21,14,14,40`. Fresh server per build. Prose/code/JSON greedy 256-token bench (2 reps) and a fixed 60-item M1
slice (20 E / 20 H / 20 U, seed 20261016, thinking off, the instrument's prompt and grader; `port_slice.py`).

| | upstream v0.7.0 `620d222` | buun `34ef0ef7c` + patch |
|---|---|---|
| loads Bolt (heterogeneous experts) | yes | yes |
| VRAM after load (MiB) | 14371 / 14135 / 13507 / 13807 | identical |
| decode, 3 prompt types | 15.14-15.23 tok/s | 14.79-14.83 tok/s (-2.6 %) |
| errors in server log | 0 | 0 |
| M1 slice, same grade as upstream | | **58 / 60** (50 byte-identical answers) |
| M1 slice grades | E 16 right; H 9 right, 2 abstained; U 12 refused | E 16; H 8 right, 1 abstained; U 12 refused |

The two differing items are hard ones (one abstention became a wrong answer, one right year became a near miss); with
50/60 answers byte-identical and different kernels underneath, that is consistent with path noise, not a port defect
(cf. `kld-needs-path-noise-control`). Bench text: 4 of 6 answers identical in their first 160 characters.

**First attempt, kept in `k8_attempt/`:** at 8 spilled layers (`-ts 18,19,15,37`, ~250-450 MB free per GPU) upstream
ran but buun returned HTTP 500 on its first request: `CUDA pool[3]: growing 206.00 MiB to 290.00 MiB failed`. Same
static allocation as upstream; buun's CUDA pool needed a little more headroom on GPU 3. Both builds were then rerun at
12 layers so they stayed comparable.

**Reading:** the cherry-pick is sound for the text model and ready to offer as a PR. On this model and card buun gives
no speed advantage (-2.6 %); its Pascal work targets paths this NVFP4/Q8 MoE does not lean on.
