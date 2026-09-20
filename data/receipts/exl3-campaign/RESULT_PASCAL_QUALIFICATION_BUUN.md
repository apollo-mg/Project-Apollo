# Result -- Pascal qualification for buun's `4d90517b1`, which shipped untested on Pascal

**2026-09-20, `.73`** (2x Tesla P100-PCIE-16GB, compute capability 6.0, CUDA 12.4).

buun's commit **`4d90517b1` "cuda: restore Pascal builds for native quantization"** (2026-09-12)
closes with:

> Validated the full SM60 server build and affected translation units for SM61/70/75/86 with CUDA
> 12.8. Runtime fallback and cache checks passed on an RTX 3090; **actual Pascal hardware
> qualification remains pending.**

He wrote the code, shipped a regression test for it, and had no Pascal to run it on. This is that
run.

## Build

| | |
|---|---|
| commit | `08826ad6` (origin/master, 2026-09-19), **548 ahead** of the node's prior checkout |
| arch | `CMAKE_CUDA_ARCHITECTURES=60` (confirmed in `CMakeCache.txt`) |
| host compiler | **gcc-13 pinned** -- CUDA 12.4's `host_config.h:143` hard-errors above gcc 13 and this box defaults to gcc 15.2 |
| result | **rc=0, zero errors**, 17:03 -> 17:22 (~20 min, 6-core 8600K, `-j 6`) |
| built into | `build_sm60_0920/` -- a NEW directory; the running daily driver (`build_sm60_head`, from `c9c52d71`) was never touched |

Prior checkout was **pre-e8m0-guard**, so this build is also the first on this node that does not
need the local CUDA 12.4 patch (`86eae269c` is now in).

## Test 1 -- `test-exl3-byte-dot`: PASS

```
PASS: all 65536 codebook products, unsigned byte sums, mixed byte dots and wrapping accumulation
EXIT CODE: 0
```

Enumerates every one of 65,536 states, checking `exl3::byte_sum` and `exl3_int8::dp4a_us` on
device against host-computed expectations, with the **mixed semantics** the commit message calls
out: `a` bytes unsigned, `b` bytes signed (`bu >= 128 ? bu - 256 : bu`), wrapping accumulation.

**The test is NOT vacuous on this hardware, which was checked before trusting the pass.** At
`__CUDA_ARCH__ == 600` both functions take the scalar `#else` branch:

```cuda
// exl3-dq.cuh: byte_sum
#elif !defined(GGML_USE_HIP) && __CUDA_ARCH__ >= 610
    return __dp4a(x, 0x01010101u, acc);
#else
    return acc + (x & 255u) + ((x >> 8) & 255u) + ((x >> 16) & 255u) + (x >> 24);
#endif
```

`__dp4a` is **sm_61**, present on GP102/GP104 (GTX 1080, P40) and **absent on GP100**. So the
branch under test is precisely the one no sm_61+ card can exercise, which is why 3090 validation
could not close this out.

## Test 2 -- `test-backend-ops test -o MUL_MAT -b CUDA0`: PASS

```
Backend 1/3: CUDA0
  1529/1529 tests passed
3/3 backends passed
```

**1529 passed, 0 failed.** 451 cases reported `not supported` and all are `type_a=tq2_0` -- a
ternary type the CUDA backend does not implement (CPU-only, cf. `3d10bcd19`). Correctly skipped,
not failures.

## Convergence worth recording

This is the **same defect, the same day, in two unrelated codebases.** Hours before this run,
`RESULT_O8_QUANTIZER_SM60.md` found that exllamav3 fails to build for sm_60 because
`quant/codebook.cuh` calls `__dp4a` unguarded -- 107 of 108 build failures, nothing to do with
tensor cores -- and fixed it with a scalar shim guarded at `__CUDA_ARCH__ < 610`.

buun's fix uses **the identical threshold and the identical remedy**, reached independently.
Two data points make it a pattern rather than a quirk: **`__dp4a` on GP100 is a systematic trap
for any project carrying EXL3-derived CUDA**, because the intrinsic is one minor revision above
the arch people mean when they say "Pascal", and the datacentre part is the one that lacks it.

## What this does NOT establish

1. **Only `MUL_MAT` was run**, not the full op suite. The daily driver was resident (~2.3 GB free
   on GPU0), so a full run risked OOM on a serving box. The rest of the suite is unrun.
2. **CUDA1 was not exercised** -- single-device run (`-b CUDA0`). The second P100 is untested.
3. **No end-to-end inference** on the new build. `test-exl3-byte-dot` and `MUL_MAT` are unit-level;
   "the server loads a model and generates correctly" is a separate claim and is unverified here.
4. **Not deployed.** The daily driver still runs `c9c52d71`. Nothing about this build is in
   production, and the `-sm tensor` determinism receipt from earlier today was taken on
   `c9c52d71` -- **a 548-commit-newer binary is a different instrument and that gate must be
   re-run** before corpus v2 relies on it.

## Suggested report upstream

Two results, one caveat, no embellishment: `test-exl3-byte-dot` PASS and `MUL_MAT` 1529/1529 on
2x P100 / sm_60 / CUDA 12.4 at `08826ad6`, with gcc-13 pinned; full op suite and multi-GPU not yet
run. That is exactly the gap `4d90517b1` left open and nothing more.
