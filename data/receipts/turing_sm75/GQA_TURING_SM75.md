# Turing (sm_75) passes the full FLASH_ATTN_EXT suite on `75a24b8f2` — comparison form correct on a third arch, and the turbo dispatcher is finally exercised

GTX 1660 Ti (TU116, compute capability **7.5**, 5,754 MiB), driver 610.43.02, on `.76`
(CachyOS live USB, Pentium G3258). Binary cross-built on `.194` for `sm_75`.
Fork `TheTom/llama-cpp-turboquant` @ **`75a24b8f2`** (GQA dispatch in comparison form).
`test-backend-ops test -o FLASH_ATTN_EXT -b CUDA0`, graphs enabled (default). Date 2026-08-02.

## Result

| metric | value |
|---|---|
| **verdict** | **2/2 backends passed — suite runs to completion** |
| OK | **7,657** |
| FAIL | **0** |
| `no device code` | **0** |
| graph-capture aborts | **0** |
| not supported (normal skips) | 5,229 |

For contrast, on RDNA4 the same suite **never completes** — it aborts on the `DKQ > 128` MLA
geometry with graphs off, and on graph capture with graphs on.

## 1. The question Tom flagged: ratios 6 and 9 on Turing

The `f924ee29f` commit message justified the modulo form by saying inequality thresholds
*"mis-tile non-power-of-2 GQA ratios"*, naming Laguna's **6** and **9**. Tom later noted that if
the mis-tiling case is real it is *"likely Turing-specific and perf-shaped — flagged in the
commit for whenever Turing hardware shows up."*

Turing showed up:

| ratio | OK | FAIL |
|---|---|---|
| `nr23=[6,1]` | **786** | **0** |
| `nr23=[9,1]` | **784** | **0** |

Zero numerical failures under the comparison form, on the exact two ratios the change was
written to fix. **Third architecture to agree** — gfx1201 (mine), sm_120 Blackwell (Tom's), now
sm_75.

Every other ratio in the suite also passes clean: `[1,1]` 3,248 · `[1,3]` 480 · `[4,1]` 1,318 ·
`[4,3]` 192 · `[8,1]` 16 · `[12,1]` 784 · `[16,1]` 16 · `[20,1]` 16 · `[32,1]` 16 — all FAIL=0.

## 2. The open question from my #249 comment, now answered

I flagged that the fork's own `ggml_cuda_flash_attn_ext_mma_turbo_switch_ncols2`
(`fattn.cu:138`) still selects `ncols2` with the old comparison form, and asked whether it needed
the same change. It is gated on `turing_mma_available(cc)` (`fattn.cu:804`), so **no AMD card can
reach it** — which is why I could only raise it as a question.

This card reaches it:

| ratio | turbo2/3/4 KV cases OK |
|---|---|
| `nr23=[6,1]` | **224** |
| `nr23=[9,1]` | **224** |

FAIL=0. **The TurboQuant MMA dispatcher handles ratios 6 and 9 correctly on Turing under the
comparison form.** The tension I raised — "either the premise is wrong or the turbo dispatcher
needs the same change" — resolves toward the first: the mis-tiling premise does not manifest as
wrong answers on any architecture tested. No change to the turbo dispatcher is indicated on
correctness grounds.

## 3. The Turing `NO_DEVICE_CODE` guard is unreachable — predicted from source, confirmed here

`fattn-mma-f16.cuh:1974-1979` carries a Turing-only guard structurally identical to the AMD one
that produced the #251 bug:

```cpp
#if __CUDA_ARCH__ == GGML_CUDA_CC_TURING
    if (ncols1*ncols2 > 32) { NO_DEVICE_CODE; return; }
#endif
```

I predicted from source that it cannot fire: `switch_ncols1` only ever selects
`ncols1 = {8,16,32,64}/ncols2`, so `ncols1*ncols2 ∈ {8,16,32,64}`, and `fattn.cu:28` contains an
explicit escape —

```cpp
if (Q->ne[1] <= 32/ncols2 || (GGML_CUDA_CC_IS_NVIDIA(cc) &&
        ggml_cuda_highest_compiled_arch(cc) == GGML_CUDA_CC_TURING) || ...)
```

— which forces the 32 branch on Turing and makes the 64 case unreachable. **Confirmed: 0
`no device code` across 7,657 cases.**

This is the fix pattern #251 asks for, already implemented four lines away in the same file: the
selector mirrors its own guard's condition. **AMD is the only path lacking it.**

## 4. `DKQ > 128` — an AMD-only restriction

The MLA geometry that aborts RDNA4 runs clean here:

| | sm_75 | gfx1201 |
|---|---|---|
| `hsk=576` (DeepSeek MLA) | **48 OK, 0 FAIL** | **abort** in `..._tile` |

So the `DKQ > 128` arm of the AMD WMMA guard is a genuine AMD-side gap, not a general
limitation of the kernel.

## Limits — read before generalising

- **TU116 has no tensor cores.** llama.cpp knows this and lists GTX 16-series in
  `turing_devices_without_mma` (`ggml-cuda.cu:363`), printing *"suboptimal performance due to a
  lack of tensor cores"* — but that list is **informational only**; `turing_mma_available()` is
  pure `cc >= 750`, so MMA still dispatches. Confirmed on the box: the warning prints and the
  run proceeds.
- Consequently this receipt supports **dispatch, compile, and correctness** claims for `sm_75`
  (all `__CUDA_ARCH__`/`cc`-keyed, so a tensor-core Turing selects identically) and supports
  **no performance claim whatsoever**. Throughput on a tensor-core-less part says nothing about
  a 2060/2080. Tom's framing was "perf-shaped"; **this card cannot test the perf half.**
- Whether a tensor-core Turing produces bit-identical values is untested; the comparison here is
  against the CPU backend within `test-backend-ops` tolerance.
- One card, one driver, one build, K=1. The run is deterministic (`2/2 backends passed`, zero
  failures), so repetition adds little — unlike the graph-capture measurements on RDNA4, which
  are nondeterministic and required K=3+.
- Graphs were left **enabled** (default) and produced zero capture aborts — the RDNA4 capture
  bug (#247/#251) does not reproduce on this vendor.

## Build provenance (cross-compilation)

`.76` is an amnesiac live USB — 7 GB RAM, 10 GB RAM-backed overlay, no nvcc — so the binary was
built on `.194` (CUDA 12.4, 40 cores) and shipped over:

- `-DCMAKE_CUDA_ARCHITECTURES=75`
- `-DGGML_NATIVE=OFF -DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_AVX512=OFF -DGGML_FMA=OFF
  -DGGML_F16C=OFF -DGGML_BMI2=OFF` — `.76`'s **Pentium G3258** has AVX/AVX2/FMA/F16C/BMI2 fused
  off (SSE4.2 only); a `-march=native` build on `.194`'s Xeon would SIGILL.
- Verified post-build rather than assumed: ISA stamp `x86-64-baseline`, and no AVX-family
  instructions in `.text`. (Ubuntu 26.04's `crt1.o` stamps baseline; CachyOS's stamps
  `x86-64-v3`, which is why this direction works and the reverse needs `objcopy`.)
- Runtime closure shipped alongside: `libggml-*`, `libllama*`, `libcudart.so.12`,
  `libcublas.so.12`, `libcublasLt.so.12`, and **`libnccl.so.2`** (230 MB — the `.194` build links
  NCCL; missing it was the one load failure). ~1 GB total into the RAM-backed overlay, leaving
  ~2.6 GB free.

## Provenance

- `logs/fa_sm75.log.gz` — full suite output; `logs/sm75_cfg.log` — CMake configure
- `logs/build_sm75.sh` — cross-build script with the portability checks
- Worktree `.194:~/tq_sm75` @ `75a24b8f2`; package `.76:~/sm75_pkg`
- Related: `../hip_rdna4/GQA_NCOLS2_RDNA4.md`, `../hip_rdna4/ISSUE249_HEAD_AND_BRANCH_RDNA4.md`

## Outcome — upstream sign-off (2026-08-03)

TheTom, on `TheTom/llama-cpp-turboquant#249`:

> parts-bin Turing service is above and beyond. Three architectures, zero failures on the exact
> ratios the modulo form was written for, and the turbo-dispatcher question closed on real sm_75
> silicon. **The Turing caveat in 75a24b8's commit message is now resolved empirically; nothing
> about that commit remains conditional.**

So this receipt's contribution is closed: it removed a stated caveat from the fix commit
(`75a24b8f2`) rather than merely corroborating it.

Related, from the same comment — the graph-capture nondeterminism documented in
`../hip_rdna4/ISSUE249_HEAD_AND_BRANCH_RDNA4.md` remains load-bearing. Tom contrasts
Chris-behind-door's deterministic repro (first decode step after long prefill, every time)
against "the stateful wandering in test-backend-ops", which is this fleet's finding; it is why
test-backend-ops could not serve as the validation workload and why a deterministic one was
worth adopting into #251's definition of done.

**Plan of record (Tom, same comment):** `launch_fattn` graph-safe temp allocation is the real fix
for both #249-long-KV and the #251/#247-family capture aborts on HIP. The test branch stays a
test branch until that lands. ⚠️ The K=15 RDNA4 capture run is deferred by Tom until the
`launch_fattn` fix exists — **do not re-offer it.**
