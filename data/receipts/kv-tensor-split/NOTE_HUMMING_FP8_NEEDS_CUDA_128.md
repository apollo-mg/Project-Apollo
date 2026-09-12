# Note — `ggml-cuda` does not build on CUDA < 12.8, for any architecture; found while qualifying buun's Pascal restore

**2026-09-12, on `.73`** (2× Tesla P100, sm_60, driver 580.178.04, **CUDA 12.4**, gcc 15.2.0).
Diagnosis is complete and verified. The Pascal qualification it blocked has since **passed** — see
`RESULT_SM60_EXL3_QUALIFICATION.md`. This note is only about the blocker found on the way.

## Context

buun merged `4d90517b1` *"cuda: restore Pascal builds for native quantization"* (2026-09-12 05:27),
reachable at `origin/master` = `9ae8f0f40`, and asked for Pascal testing — his commit message states
plainly: *"Validated the full SM60 server build and affected translation units for SM61/70/75/86 with
CUDA 12.8. Runtime fallback and cache checks passed on an RTX 3090; **actual Pascal hardware
qualification remains pending.**"*

That commit **fixes all four objects that broke our sm_60 build at `aad850104`** — verified against
that build's own log on `.73` (`~/buun-aad85/build_sm60_k.log`, built with `-k` so every failing
object is listed):

| object | error at `aad850104` | fixed in `4d90517b1` by |
|---|---|---|
| `exl3.cu` | `identifier "__dp4a" is undefined` — an sm_61+ intrinsic, absent on sm_60 | scalar SM60 fallbacks in `exl3-dq.cuh` / `exl3-gemv*.cuh` |
| `int8-channel.cu` | `identifier "__dp4a" is undefined` | the existing signed helper |
| `humming-fp8.cu` | `cuda_awbarrier_primitives.h: #error This file requires compute capability 7.0 or greater` | a guard in `humming/memory/g2s_pipeline.cuh` |
| `humming-fp8-block.cu` | the same barrier `#error` | the same guard |

`allreduce-oneshot.cu` is absent from that log; that tree carries our local guard for it
(`LOCAL_PATCH_sm60_guards.diff`), and `4d90517b1` guards it upstream too.

**Fixing the barrier exposed a fifth failure that had been there all along.** The `#error` is fatal
at preprocessing, so at `aad850104` the humming objects never got far enough to parse their FP8
types — **both old logs contain zero mentions of `e8m0`**. With the barrier guarded, compilation
proceeds and reaches them: today's log has 17. The failure was masked, not introduced, and it is
**not a Pascal problem.**

> **Correction, 2026-09-12.** The first version of this note said the commit "fixes 3 of the 4
> objects" and that the e8m0 failure "matches the 'both humming FP8' objects in our own earlier
> enumeration". Both were wrong, and both came from inferring a historical failure from present-day
> source instead of reading the historical log. It fixed all four; the humming objects originally
> failed on the barrier, not on e8m0. Commit `75c5dfc`'s message repeats the error and is superseded
> by this note.

## The failure

Built in a clean worktree at `9ae8f0f40` (`CMAKE_CUDA_ARCHITECTURES=60`, `GGML_CUDA=ON`,
`GGML_CUDA_FA=ON`, `GGML_CUDA_FA_ALL_QUANTS=OFF`, `Release`, `LLAMA_BUILD_TESTS=ON`):

```
ggml/src/ggml-cuda/humming-vendor/include/humming/datatype/base_conversion.cuh(110):
    error: identifier "__nv_fp8_e8m0" is undefined
      using scalar_t = __nv_fp8_e8m0;
(111): error: identifier "__nv_fp8x2_e8m0" is undefined
(112): error: identifier "__nv_fp8x4_e8m0" is undefined
(115): error: identifier "__nv_fp8x4_e8m0" is undefined
4 errors detected in the compilation of ".../humming-fp8.cu".
```

## Why: a toolkit floor, not an architecture guard

`__nv_fp8_e8m0` / `__nv_fp8x2_e8m0` / `__nv_fp8x4_e8m0` are the **E8M0 microscaling (MXFP8) types
NVIDIA introduced in CUDA 12.8**. Verified against the installed headers rather than assumed:

| check | result |
|---|---|
| `grep e8m0` in this box's `cuda_fp8*.h` | **no match** |
| FP8 types this toolkit *does* define | `__nv_fp8_e4m3`, `__nv_fp8_e5m2` — and nothing else |
| `CUDA_VERSION` in `cuda.h` | **12040** |
| other toolkits installed | none |

**This is why it is not a Pascal bug.** An undefined type name fails during parse, before any
architecture-dependent code generation. `CMAKE_CUDA_ARCHITECTURES` cannot affect it, and no
`__CUDA_ARCH__` guard can suppress it. **An RTX 3090 on CUDA 12.4 should fail identically** — that
follows from the mechanism and has not been tested on one. The blast radius is every user below
12.8, not the Pascal minority.

It is also **not a regression from `4d90517b1`.** `e8m0` appears 4× in `base_conversion.cuh` at
`aad850104` as well — it predates the Pascal work. On sm_60 it was masked by the barrier `#error`
above. On sm_70+ with CUDA < 12.8 nothing masks it, so it has presumably failed there all along
(inferred, not tested). buun cannot see it because he builds on 12.8.

## The fix — two lines

The E8M0 use is confined to a single template specialisation, and **neither `humming-fp8.cu` nor
`humming-fp8-block.cu` references `Float8E8M0`** — it is pulled in solely by the include, so omitting
it on older toolkits changes nothing they compile.

```diff
+#if defined(CUDART_VERSION) && CUDART_VERSION >= 12080  // __nv_fp8*_e8m0 need CUDA >= 12.8
 template <>
 class F8Conversion<Float8E8M0> {
 ...
 };
+#endif  // CUDART_VERSION >= 12080
```

Applied locally as `~/PATCH_e8m0_cuda128_guard.diff` on `.73`. **This is a declared deviation** and
must be stated in any result built from this tree. With it applied the full build completes:
`test-exl3-byte-dot` rc=0 and `llama-server` rc=0.

The alternative, if the E8M0 path is wanted unconditionally, is to document a hard CUDA 12.8 floor
for `GGML_CUDA=ON` — but that is a large requirement to carry silently, since 12.8 is recent and
distribution toolkits lag.

## Why we did not simply upgrade the toolkit

`.73` holds **34 NVIDIA/CUDA packages** deliberately, after driver drift broke CUDA on
2026-09-10. Removing that hold is a standing prohibition in this lab, so 12.4 is the environment,
and finding this bug is a direct consequence of *not* running the newest of everything. That is the
argument for a second test machine, stated concretely.

## Status and what is not claimed

- **The Pascal qualification is reported separately.** `test-exl3-byte-dot` has since been built and
  **passes on P100 hardware** (`RESULT_SM60_EXL3_QUALIFICATION.md`).
- **Note the skip trap:** `tests/CMakeLists.txt` sets `SKIP_RETURN_CODE 77` on that test. A skip must
  not be read as a pass; the return code has to be checked explicitly.
- **Nothing is claimed about EXL3 model inference on Pascal.** No EXL3 model has been obtained.
- **The patch is untested beyond compilation.** It removes a type specialisation on older toolkits;
  whether any runtime path would have wanted it on hardware that supports MXFP8 is untested here and
  irrelevant on sm_60, which cannot run those kernels anyway.
- **gcc 15.2.0 / CUDA 12.4 is an unusual pairing** and is a further difference from buun's
  environment that has not been isolated.
