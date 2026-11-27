# Patches we apply to other people's code

## `sm60-fp32-carveout.patch` -- fp32 arithmetic on Tesla P100 (sm_60)

Mainline llama.cpp enables its "fast FP16" paths for every fp16-capable NVIDIA arch except sm_61, so the P100 (sm_60)
does flash-attention tile math and cuBLAS work in half precision. Against an f32 reference this costs a median KLD of
about 0.002 and flips ~3.5 % of greedy top tokens (Qwen3.6-27B Q6_K); the patch carves sm_60 out of the three gates the
way sm_61 already is, and the same rungs fall to median KLD 0.000001 / same-top 99.9 %.
Write-up: `data/Apollo Docs/Pascal_FAST_FP16_Carveout_Results.md` (2026-07-11).

- Source: spiritbuun/buun-llama-cpp PR #80 (merged 2026-07-12); also TheTom/llama-cpp-turboquant PR #212. Those two forks
  carry it; mainline and forks built on mainline do not.
- Upstream: ggml-org/llama.cpp issue #25593, closed 2026-11-27 as not planned (stale bot, still "bug-unconfirmed").
- Applies cleanly to mainline `33aeb17f8` (2026-11-24): `git apply tools/patches/sm60-fp32-carveout.patch` in the tree.
- Effect on scored results is small: unpatched P100s vs the desktop differ in grade on 10 of 240 M1 items
  (`data/receipts/stack-drift/RESULT_STACK_DRIFT.md`). Use it for anything measured at the logit level (KLD, PPL
  comparisons, determinism), and record in a run's metadata whether the build carries it.
