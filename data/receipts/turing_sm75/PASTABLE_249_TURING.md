Turing hardware showed up. Dug a GTX 1660 Ti (TU116, cc 7.5) out of the parts bin and put it on the bench.

**`75a24b8f2` on sm_75: 7,657 OK, 0 FAIL, 0 `no device code`, 0 capture aborts, 2/2 backends passed — the full `FLASH_ATTN_EXT` suite runs to completion.** (Worth noting it never completes on RDNA4, which aborts on `DKQ > 128` with graphs off and on capture with graphs on.)

## The ratios you flagged

| ratio | OK | FAIL |
|---|---|---|
| `nr23=[6,1]` | 786 | **0** |
| `nr23=[9,1]` | 784 | **0** |

Zero numerical failures under the comparison form on exactly the two ratios the modulo change was written to fix. That's **three architectures agreeing** now — gfx1201, your sm_120, and sm_75. Every other ratio in the suite is clean too (`[1,1]`, `[1,3]`, `[4,1]`, `[4,3]`, `[8,1]`, `[12,1]`, `[16,1]`, `[20,1]`, `[32,1]` — all FAIL=0).

## The turbo dispatcher question from my last comment — answered

I'd flagged that `ggml_cuda_flash_attn_ext_mma_turbo_switch_ncols2` still uses `gqa_ratio > 4/2/1`, and couldn't test it because it's gated behind `turing_mma_available(cc)` — unreachable on AMD. This card reaches it:

| ratio | turbo2/3/4 KV cases OK |
|---|---|
| `nr23=[6,1]` | 224 |
| `nr23=[9,1]` | 224 |

FAIL=0. So the TurboQuant MMA dispatcher handles 6 and 9 correctly under the comparison form. The "either the premise is wrong or the turbo dispatcher needs the same change" tension I raised resolves toward the first — **no change indicated there on correctness grounds**, and you can close that thread.

## For #251: Turing already implements the fix you proposed

There's a Turing guard structurally identical to the AMD one:

```cpp
// fattn-mma-f16.cuh:1974
#if __CUDA_ARCH__ == GGML_CUDA_CC_TURING
    if (ncols1*ncols2 > 32) { NO_DEVICE_CODE; return; }
#endif
```

It can't fire, by construction. `switch_ncols1` only produces `ncols1*ncols2 ∈ {8,16,32,64}`, and `fattn.cu:28` has an explicit escape:

```cpp
if (Q->ne[1] <= 32/ncols2 || (GGML_CUDA_CC_IS_NVIDIA(cc) &&
        ggml_cuda_highest_compiled_arch(cc) == GGML_CUDA_CC_TURING) || ...)
```

which forces the 32 branch on Turing so the 64 case is never selected. Confirmed empirically: 0 `no device code` in 7,657 cases.

That is precisely the pattern #251 asks for — **the selector mirroring its own guard's condition — already implemented four lines away in the same file.** AMD is the only path missing it, which makes #251 less "add a new fallback" and more "make the AMD gate look like the Turing one."

Also relevant to #251: `hsk=576` (DeepSeek MLA) is **48 OK / 0 FAIL** here, versus a hard abort on RDNA4. So `DKQ > 128` is an AMD-side gap, not a kernel-wide limitation.

## Limit — please don't over-read this

**TU116 has no tensor cores.** llama.cpp lists GTX 16-series in `turing_devices_without_mma` and prints the "suboptimal performance" warning, but that's informational only — `turing_mma_available()` is pure `cc >= 750`, so MMA still dispatches. I confirmed on the box that the warning prints and the run proceeds.

So this supports **dispatch/compile/correctness** conclusions for sm_75 — all `cc`/`__CUDA_ARCH__`-keyed, so a tensor-core Turing selects identically — and supports **no performance conclusion at all**. You framed the mis-tiling case as "perf-shaped"; this card can test the correctness half and not the perf half. If someone turns up a 2060/2080, that half is still open.

Cross-built for sm_75 on the P100 box and shipped to the bench rig (the 1660 Ti is in an amnesiac live-USB machine with a Pentium G3258 — AVX/AVX2/FMA/F16C/BMI2 all fused off, so the build needed `GGML_NATIVE=OFF` plus every ISA extension explicitly disabled; verified `x86-64-baseline` ISA stamp and no AVX in `.text` before shipping).
