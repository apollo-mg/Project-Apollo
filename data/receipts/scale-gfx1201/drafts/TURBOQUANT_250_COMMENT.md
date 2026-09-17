# Draft comment for TheTom/llama-cpp-turboquant issue #250

Paste target: https://github.com/TheTom/llama-cpp-turboquant/issues/250

Note before posting: the issue is currently **closed as "not planned"** with a stale label, and
Mauricio has recent activity on it. This comment is a negative result, which is less satisfying
than a fix but narrows the search for whoever picks it up, and tells Mauricio he is not being
ignored. Re-read the thread first in case his latest messages already answer the version question.

---

Tested this on RDNA 4 to see whether it was a general HIP build failure or specific to gfx1103.
**It does not reproduce on gfx1201.**

```
commit      407f3237b (feature/turboquant-kv-cache)
cmake       -DGGML_HIP=ON -DCMAKE_HIP_ARCHITECTURES=gfx1201 -DAMDGPU_TARGETS=gfx1201 \
            -DGGML_CUDA_FA=ON -DLLAMA_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release
GPU         Radeon RX 9070 XT (gfx1201, RDNA 4), ROCm 7.2.4
result      libggml-hip.so links clean, zero undefined references
```

`GGML_CUDA_FA_ALL_QUANTS` was left at its default of `OFF`, so this is the same configuration that
fails for you, not the all-quants path.

I also checked whether it might simply have been fixed since the report rather than being
architecture-specific. It has not: the explicit instance list in the `else()` branch of
`ggml/src/ggml-cuda/CMakeLists.txt` is byte-identical between `c26cbdffc` (mid-September) and
current `407f3237b` -- 9 `turbo4_0` entries in both -- and that file has not been modified since
2026-07-31. Nothing changed that could have closed this incidentally.

So the `gfx1103` in the title looks accurate rather than incidental, and the cause is more likely
architecture-gated compilation than a missing entry in the instance list. `fattn-vec.cuh` has
`#ifdef GGML_USE_HIP` / `#ifdef RDNA` guards around the kernel body (roughly lines 76-86) which
would be the first place I would look: if a body compiles out for one architecture while the
dispatcher still references the symbol, you get exactly this link error. I have not verified that
is the mechanism, so treat it as a suggestion rather than a diagnosis.

**What my result does not establish.** gfx1103 is an RDNA 3 integrated part; gfx1201 is RDNA 4
discrete. One clean build on gfx1201 does not separate "RDNA 3 vs RDNA 4" from "integrated vs
discrete" from "gfx1103 specifically." A gfx1100 build would split the first two, and I do not
have that hardware.

@Mauricio, two things that would make this much easier to pin down: which commit you are building,
and confirmation that your `GGML_CUDA_FA_ALL_QUANTS` is also `OFF`. If you are on something older
than `407f3237b` it is worth retrying on current head first. If you are already on head, then this
is reproducible on gfx1103 and not gfx1201 on the same commit, which is a much narrower and more
actionable bug than the issue currently reads as -- and probably worth reopening under a title that
says architecture-gated rather than gfx1103-only.

Happy to run further gfx1201 builds against any commit or flag combination if that is useful. That
is the only AMD hardware I can test on directly.
