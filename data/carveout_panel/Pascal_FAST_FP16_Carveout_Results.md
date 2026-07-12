# The sm_60 FAST_FP16 Carve-Out — Killer Test Results

**Date:** 2026-07-11. **Rig:** 4× Tesla P100-PCIE-16GB (sm_60), driver 580.159, CUDA 12.4, node `.194`.
**Model:** base Qwen3.6-27B Q6_K (22,523,238,624 bytes — byte-matches buun's 3090 copy).
**Corpus:** wikitext-2 test (md5 7c0137fc034ddbc56a296bce31b4f7fb), 2048 ctx, 32 chunks.
**Builds:** stock ggml-org/llama.cpp master `4f37f5197`, arch-60-only, in two flavors:
unpatched (`~/llama_stock/build`) and patched (`~/llama_stock/build_carveout`, branch
`sm60-fp32-carveout`). All receipts: `.194:/home/mark/carveout_panel/`.

## 1. The patch (3 lines, mirrors the existing sm_61 idiom)

`ggml/src/ggml-cuda/common.cuh` — add `__CUDA_ARCH__ != 600` / `cc != 600` /
`highest_compiled_arch(cc) != 600` to the three gates that already exempt sm_61:

1. Device macro `FAST_FP16_AVAILABLE` (line 261) — governs `half2` arithmetic in
   `fattn-tile.cuh` (34 uses), `mmq.cuh` (2), `vecdotq.cuh` (6).
2. Host `fast_fp16_available(cc)` — kernel/precision selection (`fattn-tile.cuh:323`,
   `mmvf.cu:650,741`).
3. Host `fast_fp16_hardware_available(cc)` — cuBLAS compute-type selection
   (`ggml-cuda.cu:1541,1821`). This is why fa-off was equally degraded.

Historical irony, confirmed at source: sm_61 (GTX 10-series, 1/64-rate fp16) was exempted
*because its fp16 is useless*, accidentally giving it correct fp32 arithmetic. sm_60 (P100,
the fp16 flagship) got fp16 arithmetic as a reward for having good fp16 hardware. The silicon
is fine; the flag conflates "can do fp16 fast" with "should do quality-sensitive math in fp16."

## 2. Panel design

The July-10 f32-reference panel measured all rungs against an f32-KV base **computed on the
unpatched build** — so any fp16-arithmetic error *outside* the KV/attention path was common-mode
and cancelled. (Dispatch note, verified in source 2026-07-12: on sm_60 MMQ never runs —
`ggml_cuda_should_use_mmq` returns false below `GGML_CUDA_CC_DP4A`=610, a check that precedes
even the `GGML_CUDA_FORCE_MMQ` override — so quantized-weight prefill is dequantize + cuBLAS
GEMM, whose compute type is selected by gate #3. The weight-path fp16 error measured in Cell 0
is therefore attributable to the cuBLAS fp16 compute path, not MMQ.)
Today's panel therefore:

- **Cell 0:** patched f32-faoff vs *unpatched* f32 base — direct measurement of the previously
  invisible common-mode arithmetic error. Same weights, same f32 KV, only the math differs.
- **New truth base:** f32 KV, fa off, generated on the **patched** build.
- **Cells 1–3:** patched f16-faoff / f16-faon / q8-faon vs the patched base — the killer-test
  readout scored against predictions logged the night before.
- **Speed legs:** patched-vs-unpatched llama-bench, pp8192 @ d8192 + tg32, f16 and q8_0 KV.

## 3. Results — quality (all medians; full stat blocks in receipts)

**Cell 0 (arithmetic-only delta, fp16 math vs fp32 math):**
median KLD **0.004962**, mean 0.023987, 99.9% 4.91, max 23.7, max Δp 98.9%,
**same-top 95.002%** — the arithmetic mode alone flips 1 in 20 greedy tokens, and ~1/1000
tokens gets its distribution essentially replaced. This component is ~2× the attention-path
effect and was invisible to every prior measurement. (Mark called the weight-path question
before the number existed.)

**Cells 1–3 vs predictions (logged 2026-07-10, memory + Discord):**

| rung | unpatched median KLD (Jul 10) | predicted | patched median KLD | same-top: unpatched → patched |
|---|---|---|---|---|
| f16-faoff | 0.002298 | ~0.0002 | **0.000001** | 96.47% → **99.89%** |
| f16-faon  | 0.002127 | converge | **0.000000** | 96.45% → **99.93%** |
| q8-faon   | 0.002164 | converge | **0.000005** | 96.52% → **99.80%** |

Predictions confirmed and beaten by ~two orders of magnitude. The "Pascal scatter sphere" was
**100% arithmetic, 0% storage**. True q8_0 KV cost on corrected Pascal: median ~5e-6 —
effectively free, now with correct ordering (q8 slightly below f16, as physics demands).

## 4. Results — speed (the price of the fix)

pp8192 @ d8192, tg32 @ d8192, 4× P100 layer-split, same model:

| config | patched | unpatched | delta |
|---|---|---|---|
| f16 KV prefill | 318.53 ± 0.53 t/s | 318.60 ± 0.35 t/s | **tie** |
| f16 KV tg      | 8.64 ± 0.00 t/s   | 8.51 ± 0.01 t/s   | +1.5% patched |
| q8_0 KV prefill| 312.60 ± 0.36 t/s | 312.52 ± 0.33 t/s | **tie** |
| q8_0 KV tg     | 8.46 ± 0.01 t/s   | 8.34 ± 0.01 t/s   | +1.4% patched |

**The fix is free on this model** (decode a hair faster patched, both KV types — possibly reduced
fp16↔fp32 conversion overhead; treat as parity). The logged prediction (prefill −20–40%) was
WRONG in the favorable direction — recorded per protocol.

**Dense full-attention control (closes the stated limit):** FastContext 4B (`qwen3` arch — true
dense, attention every layer), single P100, f16 KV, pp8192 @ d8192 — the worst-case shape for
an fp32-attention penalty (small model + deep context = maximal attention compute share):

| config | patched | unpatched |
|---|---|---|
| dense 4B prefill | 357.90 ± 0.05 t/s | 357.96 ± 0.07 t/s |
| dense 4B tg      | 53.30 ± 0.05 t/s  | 53.30 ± 0.05 t/s  |

Exact tie, both metrics (receipts: `bench_dense4b_{patched,unpatched}.log`). **The fix is free on
hybrid AND dense.** Implication: the fp16 fast path on sm_60 buys no measurable throughput in
real attention workloads — the tile kernel is bound elsewhere (memory/occupancy), so P100 owners
were paying the full precision cost for zero speed benefit. The upstream case is now unconditional:
carve-out with no tradeoff, matching how sm_61 is already treated.

### Independent verification (TheTom, on merging turboquant PR #212, 2026-07-12)

Tom's pre-merge review independently confirmed: (a) **the three gates are the only 600-vs-610
distinction anywhere in the CUDA tree**, so the carved sm_60 path is preprocessor-identical to
the long-proven sm_61 path; (b) **a Blackwell build showed bit-identical PPL with decode
unchanged** — direct evidence the patch is a no-op on non-Pascal arches. Both fork PRs:
buun-llama-cpp #80, llama-cpp-turboquant #212 (merged).

## 5. The open cross-arch lead (unproven, load-bearing next step)

Patched-Pascal q8 median (5e-6) reads ~44× tighter than buun's stock-3090 q8 (0.000222 @
matched 2k/32ch). **Reference frames differ** (his: q8-vs-f16, both fa-on, within-build; ours:
q8-faon vs f32-faoff truth base), so this is suggestive only. buun's 3090 mirror-decomposition
panel (4 commands, already relayed) decides it: if Ampere shows its own ~0.0002 floor vs f32
truth (fp16-accumulate MMA tax), then **a patched P100 is the numerically cleanest instrument
in the study** — and the README quality tables across the ecosystem are Ampere-relative, not
truth-relative.

## 6. Implications

- Every Pascal card running llama.cpp (except ironically the GTX 10-series) carries a removable
  ~0.005-median-KLD / 5%-token-flip arithmetic tax on all workloads — KV quantization or not.
- Reproducibility narrative: same weights + same sampler + different arch = 1-in-20 different
  greedy tokens, mechanically explained and toggleable with one build flag.
- VBR/TCQ codec evaluations on Pascal were conducted inside the fog; orderings held (validated
  Jul 10) but absolute numbers should be re-read post-patch.
