# A 3-line fork-only GQA change makes flash-attention uncompilable on RDNA4 — confirmed by targeted revert

RX 9070 XT (gfx1201, HIP arch 1300), ROCm, `llama-cpp-turboquant` @ `55580fe0c`
("hip: add mixed f16/bf16 + q8_0 fattn-vec instances to the HIP build (#249)"), 2026-08-02.
`test-backend-ops test -o FLASH_ATTN_EXT -b ROCm0`, `GGML_CUDA_DISABLE_GRAPHS=1`.

## Result

| arm | cases OK | FAIL | `no device code` | died at | in |
|---|---|---|---|---|---|
| **head** (`55580fe0c`, modulo) | 2,668 | 0 | **47** | `hsk=128,hsv=128,nh=4,nr23=[9,1]` | *(lost — see Limits)* |
| **revert** (head − `f924ee29f`'s fattn.cu hunk) | **7,604** | 0 | **0** | `hsk=576,hsv=512,nh=1,nr23=[1,1]` | `ggml_cuda_flash_attn_ext_tile` |

Reverting **three lines** removes the failure class entirely and lets the suite run **2.85× further**.

## Mechanism

`f924ee29f` (TheTom, 2026-07-22, *"laguna: MoE down-proj f16-overflow guard + CUDA GQA ratio
fix"*) changed `ggml_cuda_flash_attn_ext_mma_f16_switch_ncols2` in `ggml/src/ggml-cuda/fattn.cu`:

```diff
-    if (use_gqa_opt && gqa_ratio > 4) {   ncols2 = 8
+    if (use_gqa_opt && gqa_ratio % 8 == 0) {
-    if (use_gqa_opt && gqa_ratio > 2) {   ncols2 = 4
+    if (use_gqa_opt && gqa_ratio % 4 == 0) {
-    if (use_gqa_opt && gqa_ratio > 1) {   ncols2 = 2
+    if (use_gqa_opt && gqa_ratio % 2 == 0) {
```

For **`gqa_ratio = 9`**, 9 is divisible by none of 8/4/2, so selection falls through to
**`ncols2 = 1`**. `fattn-mma-f16.cuh:1983` refuses that on AMD:

```cpp
#if defined(AMD_WMMA_AVAILABLE)
    if (ncols1*ncols2 < 16 || ncols2 == 1 || DKQ > 128) { NO_DEVICE_CODE; return; }
#endif
```

Under the old form `9 > 4` → `ncols2 = 8`, which compiles. The AMD WMMA path has **no
`ncols2 == 1` instance and no dispatcher fallback to the vec path**, so the hole was always
there — the GQA change is what started routing shapes into it.

### Why only ratio 9, and not ratio 1 — which also yields `ncols2 = 1`

`gqa_ratio = 1` falls through to `ncols2 = 1` under **both** forms, yet `nr23=[1,1]` passes
everywhere (1,264 OK on the head arm). It is not reached by this path at all:

- `fattn.cu:531` — `gqa_opt_applies = gqa_ratio >= 2 && ...`. At ratio 1 this is **false**, so
  both AMD MMA gates (`:692`, `:731`) are skipped and the shape goes to vec/tile.
- `fattn.cu:706-714` — the RDNA4 selector doubles `gqa_ratio_eff_rdna4` while
  `gqa_ratio % (2*eff) == 0`. For **odd** ratios it stays 1, so MMA is chosen only when
  `Q->ne[1] * 1 > 8`.

So the failure needs all three: `gqa_ratio >= 2`, `gqa_ratio` odd (eff stays 1), and
`Q->ne[1] > 8`. **Ratio 9 is the only value in the suite that satisfies all three.** Ratio 6 is
even → `eff = 2` → `6 % 2 == 0` → `ncols2 = 2`, which clears the guard. Confirmed on the revert
arm: `hsk=128, nr23=[9,1]` is **OK at nb = 1, 3, 32 and 75**, i.e. both below and above the
`Q->ne[1] > 8` threshold that selects MMA.

The failing shapes are `type_K=turbo4,type_V=turbo4`, which reach this f16 dispatcher via
`ggml_cuda_flash_attn_ext_mma_f16` (`fattn.cu:198`); the fork's own turbo dispatcher
(`ggml_cuda_flash_attn_ext_mma_turbo_switch_ncols2`) is gated to "turing MMA" and is not on the
AMD path.

## This is a fork divergence, not inherited from upstream

Upstream `llama.cpp` @ `0fcb3760b` (`engines/llama_cpp_latest`) carries the **asymmetry
deliberately**: modulo in the Volta branch, comparison in the non-Volta branch.

| | Volta branch | non-Volta branch |
|---|---|---|
| upstream `0fcb3760b` | `% 8/4/2 == 0` (l.68-78) | `> 4/2/1` (l.87-97) |
| fork parent `e1fd6cea3` | `% 8/4/2 == 0` | `> 4/2/1` |
| fork head `55580fe0c` | `% 8/4/2 == 0` | **`% 8/4/2 == 0`** ← changed |

Commit message states it is a *"Port of poolside/llama.cpp laguna branch (04b2b72c) onto this
fork"* — i.e. from a third-party branch, not from ggml-org master. On upstream, RDNA4 gets
`ncols2 = 8` at `gqa_ratio = 9` and does not hit the guard.

## The premise behind the change does not reproduce as wrong answers here

The commit's stated motivation is that inequality thresholds *"mis-tile non-power-of-2 GQA
ratios"*, naming Laguna's ratios **6** and **9**. On this hardware, with the comparison form
restored:

| ratio | revert arm | head arm |
|---|---|---|
| `nr23=[6,1]` | **784 OK, 0 FAIL** | 112 OK (then death) |
| `nr23=[9,1]` | **784 OK, 0 FAIL** | 56 OK (then death) |
| `nr23=[9,1]`, turbo4 only | **112 OK** | 8 OK |

`test-backend-ops` compares against the CPU backend, so `FAIL=0` means numerically matching
within tolerance. The gap between lines printed (1,232) and OK (784) per ratio is
`not supported [ROCm0]` — normal backend skips for quantized KV combos (q4_1/q5_0/q5_1/iq4_nl),
not hidden failures. **On gfx1201 the comparison form computes correct results for exactly the two
ratios the change was written to fix.**

**This does not show the change is wrong on CUDA.** The commit says it is "exercised in Phase
2b", and no NVIDIA MMA hardware was available here to test it (the fleet's P100s are sm_60 and
do not take the WMMA/MMA path). The finding is scoped to AMD.

## Recommendation

**Not a revert** — that would undo whatever CUDA correctness the change buys. The defect is that
the AMD WMMA path can be handed a configuration it never implements. Either:

1. add `ncols2 == 1` instances for AMD WMMA, or
2. have the dispatcher fall back to the vec path when the WMMA guard would reject the selection,
   instead of selecting a combination and failing at kernel-launch time.

A dispatcher that can select an uncompiled instance will keep producing this class of bug as
new ratios appear.

## Open question for the fork: the TurboQuant MMA dispatcher was not updated

`f924ee29f` changed `ggml_cuda_flash_attn_ext_mma_f16_switch_ncols2`. The fork's **own**
`ggml_cuda_flash_attn_ext_mma_turbo_switch_ncols2` (`fattn.cu:138`) still selects `ncols2` with
the old comparison form:

```cpp
// fattn.cu:165-173
if (use_gqa_opt && gqa_ratio > 4) {   // ncols2 = 8
if (use_gqa_opt && gqa_ratio > 2) {   // ncols2 = 4
if (use_gqa_opt && gqa_ratio > 1) {   // ncols2 = 2 -> (4,2)
```

It is reached (`fattn.cu:803-816`) when `GGML_TURBO_MMA_FUSED` is on (**default on**), K==V is
TURBO2_0/TURBO3_0/TURBO4_0, `Q->ne[1] <= 4`, `Q->ne[0]` is 128 or 256, and
`turing_mma_available(cc)`.

That last gate is why AMD never reaches it — and why turbo4 KV falls through to the f16
dispatcher on RDNA4, which is the mechanism above. But it also means: **if the commit's premise
is right — that comparison thresholds mis-tile ratios 6 and 9 — then on CUDA Turing+ the
TurboQuant KV path still mis-tiles exactly those ratios**, by default, in the feature the fork
exists for.

So the open question for the maintainer is simply: **does the turbo dispatcher need the same
change, or does its packing differ such that the comparison form is correct there?** It is
plausible that it differs — the turbo dispatcher is type-parametric, gated to `Q->ne[1] <= 4`,
and its own comment (`fattn.cu:118`) declares a *fixed* reachable set
`{(1,8),(2,8),(4,8),(2,4),(4,4),(4,2),(8,1)}`, which may handle the remainder differently from
the f16 path.

This cannot be tested here: the fleet has no Turing+ NVIDIA hardware (the P100s are sm_60,
pre-Turing, and fail `turing_mma_available`). Flagged, not claimed.

## Two adjacent defects, reported separately

- **Graph capture.** With graphs enabled, `FLASH_ATTN_EXT` aborts on **both** arms:
  `ROCm error: operation not permitted when stream is capturing` at `ggml-cuda.cu:108`,
  immediately after `CUDA graph warmup complete`. This is the #247 class reproducing on a second
  vendor. `GGML_CUDA_DISABLE_GRAPHS=1` is therefore part of the measurement, not a fix.
- **`DKQ > 128`.** The revert arm dies later in `ggml_cuda_flash_attn_ext_tile` on
  `hsk=576,hsv=512` (DeepSeek MLA geometry) — the `DKQ > 128` arm of the same guard, a separate
  hole on the same path.

## Why the parent commit was not built instead

The obvious experiment — build `f924ee29f^` — is impossible. **`e1fd6cea3` does not compile at
all**, and neither does `f924ee29f`:

- `src/llama-model.h`: `LLM_TYPE_118B_A8B` declared twice (l.126, l.134)
- `src/models/models.h`: `struct llama_model_laguna` defined twice (l.1287, l.1727)

These cascade into ~16 `duplicate case value` errors in `llama-model.cpp` and take out the core
`llama` target, not just HIP. Both duplications are fixed by `55580fe0c`. Reverting the 3-line
hunk on the head is also the better design: **one variable changes**, with compiler, flags,
ROCm, and every other fork patch held identical.

## Limits

- **The head arm's failing descriptor is lost.** `test-backend-ops` writes descriptors to stdout
  (block-buffered to a file) and errors to stderr (unbuffered); the process dies mid-burst and
  the log ends mid-line, so unflushed descriptors never land. `nr23=[9,1]` is the last
  *surviving* line before the errors, **not** a confirmed identification of the failing case.
  The causal claim rests on the revert A/B, not on that line. A re-run under `stdbuf -o0` would
  pin the exact shape.
- Same cause: the `no device code` count is **not stable** — 23 in the first run, 47 in the
  A/B run. It counts how many launches escaped before death, not how many shapes are affected.
- One GPU, one arch (gfx1201/1300), one ROCm version. Not tested: RDNA3, CDNA, or any NVIDIA MMA
  hardware.
- Both arms crash; neither completes the suite. This measures *how far* each gets, and the
  revert arm's later crash is a different, pre-existing defect.

## Provenance

- Script `scratchpad/gqa_ab.sh`; run log `logs/gqa_ab.log`
- `logs/gqa_head_fa.log.gz`, `logs/gqa_revert_fa.log.gz` — full suite output, both arms
- `logs/hip_fa.log.gz` (graphs on, aborts), `logs/hip_fa_nograph.log.gz` (first head run)
- `logs/hip_cfg.log` — HIP configure; `logs/pregqa_build_errors.txt` — parent-commit failure
- Worktree `/mnt/TG_2TB/tmp_pr244` @ `55580fe0c`, restored to head after the A/B
- Prior HIP coverage this session: **TURBO_WHT 27/27**, **SET_ROWS 159/159** on ROCm0
