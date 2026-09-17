# Result -- the gfx1103 HIP flash-attention link failure does NOT reproduce on gfx1201

**2026-09-17.** Negative result, recorded because it narrows an open question rather than
answering it. Prompted by TheTom/llama-cpp-turboquant issue #250 (opened 2026-08-02 by `dackmmc`,
closed as "not planned" with a stale label, revived by a second reporter on 2026-09-17).

## The question

#250 reports that a HIP build with `GGML_CUDA_FA=ON` fails to link `libggml-hip.so` on gfx1103
(Radeon 780M, RDNA 3 integrated), with `undefined reference to ggml_cuda_flash_attn_ext_vec_case<...>`.
The reporter's own diagnosis was that template instantiations were missing from the HIP build.

**My hypothesis, stated before testing: the gfx1103 in the title is a red herring.** A missing
template-instantiation list would be architecture-independent, so it should reproduce on any HIP
target with FA enabled, including gfx1201.

## Result: hypothesis WRONG

```
commit      407f3237b (feature/turboquant-kv-cache)
cmake       -DGGML_HIP=ON -DCMAKE_HIP_ARCHITECTURES=gfx1201 -DAMDGPU_TARGETS=gfx1201
            -DGGML_CUDA_FA=ON -DLLAMA_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release
GPU         RX 9070 XT (gfx1201, RDNA 4), ROCm 7.2.4
result      libggml-hip.so links clean, ZERO undefined references
```

`GGML_CUDA_FA_ALL_QUANTS` was left at its default `OFF`, so this is the same configuration that
fails on gfx1103, not the all-quants path (confirmed from `CMakeCache.txt`).

## Ruling out "it was already fixed"

The explicit instance list in the `else()` branch of `ggml/src/ggml-cuda/CMakeLists.txt` is
**byte-identical** between `c26cbdffc` (the local checkout, PR #225) and current `407f3237b`:
9 `turbo4_0` entries in both, and 25 explicit instances total. That file has not been modified
since 2026-07-31. Nothing changed that could have closed this incidentally, so the clean build is
a real architecture difference and not a version artifact.

The enumeration is also more complete than the reporter assumed: all pairwise combinations of
turbo2_0 / turbo3_0 / turbo4_0 plus f16 and q8_0 pairings are present in the non-ALL_QUANTS list.

## Where the cause probably is (unverified)

`ggml/src/ggml-cuda/fattn-vec.cuh` carries `#ifdef GGML_USE_HIP` / `#ifdef RDNA` guards around the
kernel body at roughly lines 76-86. If a body compiles out for one architecture while the
dispatcher still emits a reference to the symbol, the result is exactly this link error, and it
would be architecture-specific. **Not verified.** Recorded as the first place to look, not as a
diagnosis.

## What this does not establish

gfx1103 is RDNA 3 **integrated**; gfx1201 is RDNA 4 **discrete**. One clean build on gfx1201 does
not separate "RDNA 3 vs RDNA 4" from "integrated vs discrete" from "gfx1103 specifically." A
gfx1100 build (RDNA 3 discrete) would split the first two. That hardware is not in the fleet.

## Disposition

Posted as a comment on #250 with the above, plus a request to the active reporter for their commit
hash and `GGML_CUDA_FA_ALL_QUANTS` setting. If they are on current head, the bug is reproducible on
gfx1103 and not gfx1201 at the same commit, which is narrower and more actionable than the issue
currently reads, and probably worth reopening under an architecture-gated title.

Worktree left at `/mnt/TG_2TB/experiments/tq-gfx1201-fa` for follow-up builds.
