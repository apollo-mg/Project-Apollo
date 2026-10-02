**Title:** CUDA: one warp per row for short-row float mat-vec (mmvf) on pre-Volta NVIDIA

## What

For `ncols <= 1536`, `mul_mat_vec_f` now launches with `block_size == warp_size` and 2 rows per block, instead of one
block of up to 256 threads per row. This is the same idea as MMVQ's `small_k` path (#20635).

- **Why it was slow:** with short rows, the old launch leaves most threads with a single multiply-add, and every row
  pays a cross-warp shared-memory reduction plus barriers. At k=320, m=10240 on a P100 (1063 MHz), F16, BF16 and F32
  all took 80-82 us, against 23 us for Q8_0 on the same shape.
- **How the change is structured:**
  - `rows_per_block` is a template parameter (default 1), so the default launch compiles to unchanged code.
  - The multi-row instantiation exists only beside `block_size == 32`.
  - The bounds check is under `if constexpr (rows_per_block > 1)`.
  - The 32-thread instantiation has no barrier, so a whole warp returning early is safe.
- **Gated to pre-Volta NVIDIA**, the only hardware I could measure (P100, sm_60). Other GPUs keep the existing launch
  (see "Testing on newer cards" below).

## Results (P100, sm_60)

**Kernel** (`test-backend-ops perf`, this PR's commit vs current master `082b72c5e`, P100 at 1063 MHz, median of
3 interleaved reps):

| shape (type, m, n, k) | master | this PR | ratio |
|---|---:|---:|---:|
| BF16 10240x1x320 | 82.1 us | 27.0 us | 0.329 |
| F32 10240x1x320 | 80.3 us | 27.6 us | 0.344 |
| F16 4096x1x448 | 47.2 us | 14.1 us | 0.300 |
| F16 32000x2x192 | 188.0 us | 73.7 us | 0.392 |
| BF16 2048x1x256 | 15.4 us | 6.4 us | 0.415 |
| BF16 8192x8x640 | 220.7 us | 116.4 us | 0.527 |
| F32 16384x1x96 | 54.1 us | 30.1 us | 0.557 |
| F16 4096x1x4096 (long rows, unchanged path) | 84.7 us | 84.7 us | 1.000 |
| BF16 320x1x10240 (few rows, unchanged path) | 21.0 us | 21.0 us | 1.000 |

The same shapes gave the same ratios on a second P100 box at 1328 MHz (0.30-0.56).

- **None of these shapes were used for tuning.** The tuning grid (F16, m=10240, k 64-2048, n 1 and 4) picked 2 rows
  per block and the k cutoff.
- **Worst case anywhere: 1.01x**, at k=64, n=4, where every variant sits at the ~20 us harness floor.

**End to end:**
- Qwen3.8-Flash-Next GSQ-RCO IQ3_XXS on 4x P100 has 192 BF16 hyper-connection matrices, 96 of them 10240x320 per
  token.
- Decode goes **18.78 -> 20.90 tok/s (1.11x)**: 4 fresh servers in ABBA order, 12 requests per build.
- That matches what converting those tensors to Q8_0 bought (1.12x), without changing the weights.

## Correctness

- **`test-backend-ops test`** (MUL_MAT, MUL_MAT_ID, MUL_MAT_VEC_FUSION, F16/BF16/F32) on this commit:
  **1130/1130**, which is master's 1061 plus the 69 cases this PR adds. During development, a wider set of 192
  short-row cases also passed:
  - row counts 7 / 1001 / 10241;
  - n = 1-8, k = 64-1024;
  - a strided k view and broadcast;
  - MUL_MAT_ID with and without broadcast;
  - gate+bias fusion.
- **This PR adds a compact subset of those cases (69 eval cases)**, so CI covers the new path, plus 7 perf cases for
  the shapes above.
- **The default path is unchanged:** 22 default instantiations were compared, with function names and addresses
  stripped. That covers F16 (half and float accumulators), BF16 and F32 at blocks 160/256, n=1/4, fusion and
  multi-token ID. All have identical SASS before and after. A first version with a runtime row index cost the default
  path 3-4 %, which is why `rows_per_block` is a template parameter.
- **Model-level KLD at `-ub 1`** (so decode kernels actually run): 0.0139 vs base.
  - Not zero, because summation order changed. But the unpatched build's own prefill-vs-decode paths diverge by
    0.0144 on this model, so the kernel change is inside the model's noise floor.
  - PPL ratio +0.002 +/- 0.003.
- **HIP:** `mmvf.cu` builds for gfx1201 and gfx90a (warp 64). The new instantiation exists there but is never
  launched.

## Testing on newer cards

**@spiritbuun:** if you have a minute on the 3090, the quickest check is:
1. Locally change `cc < GGML_CUDA_CC_VOLTA` to `true` in `launch_mul_mat_vec_f_cuda`.
2. Compare before and after with
   `test-backend-ops perf -b CUDA0 -o MUL_MAT -p 'm=(10240|4096|32000|8192),n=(1|2|8),k=(320|448|192|640|4096),bs=\[1,1\],nr=\[1,1\]'`.
   That runs the 7 perf cases this PR adds (plus 3 stock ones).

If it holds on Ampere, the gate can widen. The k cutoff and rows-per-block were tuned on sm_60 only.

Full method, raw data and pre-registration:
https://github.com/apollo-mg/Project-Apollo/blob/main/data/receipts/sm60-types/RESULT_MMVF_SHORTROW.md

(Test designed and run with my agent, Claude; I reviewed it before posting.)
