# Note — O11: does buun's upstreamed e8m0 guard remove our local patch? (predictions before the result)

**Written 2026-09-13 ~11:00, while the build is still linking.**

O11 has been open since the campaign started: our sm_60 builds carry a local 2-line guard
(`kv-tensor-split/PATCH_e8m0_cuda128_guard.diff`) because humming's `__nv_fp8_e8m0` types break
`ggml-cuda` on any CUDA below 12.8, and the fleet is on 12.4. buun's **`86eae269c` — "cuda: guard
Humming E8M0 conversion on older toolkits"** should make that unnecessary.

**The test:** a clean worktree of `da458765d` on `.73` at `/mnt/HDD/buun-da458`, `git status` empty (no
patch), configured `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60`, building `llama-server`,
`llama-perplexity`, `llama-bench` and his four EXL3 test targets.

| id | prediction |
|---|---|
| P-O11a | The build completes with `BUILD EXIT 0` on CUDA 12.4 with **no local patch** — which retires O11 |
| P-O11b | buun's EXL3 tests pass on **sm_60**, as they did on gfx1201 yesterday: every `test-exl3-*` returns 0 or the skip code 77 |

**Declared:** `test-exl3-byte-dot` returning 77 (skip) is not a pass for the kernel, only for the harness;
on RDNA4 it genuinely passed, and the P100 result is recorded either way.
