Picked up `55580fe0c` and ran it on RDNA4 hardware — RX 9070 XT (gfx1201, wave32, 16 GB), ROCm 7.2.4. Since the note was that there's no HIP hardware in the fleet, here's what the backend does on a real card.

**The build fix works.** Links clean, `test-backend-ops` runs. On non-FA ops the HIP backend looks healthy:

- `TURBO_WHT` — **27/27**
- `SET_ROWS` — **159/159**

`FLASH_ATTN_EXT` turned up two independent problems.

---

## 1. Graph capture aborts (probably #247 on a second vendor)

With graphs enabled, `FLASH_ATTN_EXT` dies immediately after `CUDA graph warmup complete`:

```
ROCm error: operation not permitted when stream is capturing
  ggml-cuda.cu:108
```

Same class as #247. Everything below is with `GGML_CUDA_DISABLE_GRAPHS=1`, so that's part of the measurement, not a workaround I'm recommending.

## 2. `ncols2 == 1` has no AMD WMMA instance — bisected to `f924ee29f`

With graphs off, the suite gets partway and then dies in a burst of:

```
fattn-mma-f16.cuh:1983: ERROR: HIP kernel flash_attn_ext_f16
  has no device code compatible with HIP arch 1300
```

I bisected it with a targeted revert rather than by commit, for a reason in the footnote. Reverting **only** the `fattn.cu` hunk of `f924ee29f` ("laguna: MoE down-proj f16-overflow guard + CUDA GQA ratio fix") on top of `55580fe0c`:

| arm | cases OK | FAIL | `no device code` | died at |
|---|---|---|---|---|
| `55580fe0c` as-is | 2,668 | 0 | 47 | `hsk=128,nh=4,nr23=[9,1]` |
| same, minus that 3-line hunk | **7,604** | 0 | **0** | `hsk=576,hsv=512` in `..._tile` |

Three lines, and the suite runs 2.85× further. (The revert arm's later death is a separate pre-existing thing — `DKQ > 128` on the MLA geometry, same guard, different arm.)

### Mechanism

The hunk changed `ggml_cuda_flash_attn_ext_mma_f16_switch_ncols2`:

```diff
-    if (use_gqa_opt && gqa_ratio > 4) {        // ncols2 = 8
+    if (use_gqa_opt && gqa_ratio % 8 == 0) {
```

At **`gqa_ratio = 9`**, 9 divides by none of 8/4/2, so selection falls through to `ncols2 = 1`. `fattn-mma-f16.cuh:1982` refuses that on AMD:

```cpp
#if defined(AMD_WMMA_AVAILABLE)
    if (ncols1*ncols2 < 16 || ncols2 == 1 || DKQ > 128) { NO_DEVICE_CODE; return; }
#endif
```

Under the old form `9 > 4` → `ncols2 = 8`, which compiles.

**To be clear about where the defect is: I don't think the modulo change is wrong.** The AMD WMMA path has no `ncols2 == 1` instance and the dispatcher has no fallback to vec — that hole predates the commit. The GQA change just started routing shapes into it.

Why only ratio 9, when ratio 1 also yields `ncols2 = 1`: `gqa_opt_applies = gqa_ratio >= 2` (`fattn.cu:531`), so ratio-1 shapes never enter the AMD MMA gates. And the RDNA4 selector (`fattn.cu:706-714`) doubles `gqa_ratio_eff_rdna4` only while `gqa_ratio % (2*eff) == 0`, so odd ratios keep `eff = 1` and reach MMA only when `Q->ne[1] > 8`. Ratio 9 is the only value in the suite that is ≥2, odd, and tested above that threshold. Ratio 6 is even → `ncols2 = 2` → clears the guard.

### One thing that argues against the stated motivation

The commit message says inequality thresholds mis-tile non-power-of-2 ratios, naming 6 and 9. On gfx1201 with the comparison form restored, those two ratios are numerically fine against the CPU reference:

| ratio | OK | FAIL |
|---|---|---|
| `nr23=[6,1]` | 784 | **0** |
| `nr23=[9,1]` | 784 | **0** |

including 112 `turbo4` cases at ratio 9, at `nb` = 1, 3, 32 and 75 — both sides of the `Q->ne[1] > 8` threshold that selects MMA.

That's AMD only. I have no Turing+ NVIDIA hardware to check the CUDA case the commit was actually written for, so this isn't me saying the change is unnecessary — just that on this backend the old form computed correct results for exactly those ratios.

### Suggested fix

Not a revert — that would undo whatever CUDA correctness this buys. Either add `ncols2 == 1` instances for AMD WMMA, or have the dispatcher fall back to vec when the WMMA guard would reject its selection, instead of picking a combination and failing at launch. A dispatcher that can select an uncompiled instance will keep producing this as new ratios show up.

---

## Question: was `..._mma_turbo_switch_ncols2` meant to change too?

`ggml_cuda_flash_attn_ext_mma_turbo_switch_ncols2` (`fattn.cu:165-173`) still selects with `gqa_ratio > 4/2/1`. It's reached (`fattn.cu:803`) when `GGML_TURBO_MMA_FUSED` is on — **default on** — with TURBO2/3/4 K==V, `Q->ne[1] <= 4`, D ∈ {128,256}, and `turing_mma_available(cc)`.

That last gate is why AMD never reaches it (and why turbo4 KV falls through to the f16 dispatcher here, which is how I hit this at all). But it also means that if the mis-tiling premise holds, the TurboQuant KV path would still mis-tile ratios 6 and 9 on CUDA Turing+, by default.

Genuinely a question, not a claim — the turbo dispatcher is type-parametric with its own declared reachable set `{(1,8),(2,8),(4,8),(2,4),(4,4),(4,2),(8,1)}`, so its packing may differ and the comparison form may be correct there. I can't test it: no Turing+ NVIDIA hardware here.

---

## Footnote: why a targeted revert instead of building the parent

`f924ee29f^` (`e1fd6cea3`) doesn't compile, and neither does `f924ee29f`:

- `src/llama-model.h` — `LLM_TYPE_118B_A8B` declared twice (l.126, l.134)
- `src/models/models.h` — `struct llama_model_laguna` defined twice (l.1287, l.1727)

Those cascade into ~16 `duplicate case value` errors and take out the core `llama` target, not just HIP. Both are fixed by `55580fe0c`. Relevant to this issue's rebase theme — there's a window of commits that can't be bisected through. Reverting the hunk on the head is the better experiment anyway: one variable, everything else identical.

## Limits

- One GPU, one arch (gfx1201 / HIP arch 1300), ROCm 7.2.4. Not tested on RDNA3, CDNA, or any NVIDIA MMA hardware.
- The failing descriptor isn't pinned. `test-backend-ops` block-buffers descriptors to stdout and writes errors unbuffered to stderr; the process dies mid-burst, so the last descriptor in the log is the last one *flushed*, not the one that failed. Same reason the error count isn't stable (23 in one run, 47 in another) — it counts launches that escaped before death. The causal claim rests on the A/B, not on that line.
- Both arms crash; neither completes the suite. This measures how far each gets.
- `not supported [ROCm0]` lines (quantized KV combos) are excluded from the OK counts above.

Happy to run more on this card — it's the only RDNA4 in my setup and it's free for it.
