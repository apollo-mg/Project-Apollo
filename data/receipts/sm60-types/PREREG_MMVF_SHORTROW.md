# Pre-registration: one warp per row for short float mat-vec rows (`mmvf.cu`) on sm_60

**Registered 2026-10-01, before any timed row.** Follows `RESULT_HC_Q8.md` (09-29). There, F16, F32 and BF16 mat-vec
at k=320, m=10240 all took ~81 us against Q8_0's 23 us. Converting GSQ-RCO's 192 BF16 hyper-connection matrices to
Q8_0 recovered 1.13x decode, at a KLD cost of 0.015. That receipt named the kernel as "the better fix". Mark agreed
the order on 10-01 ("Sure let's take a look at your suggested ordering").

**Prior art checked:** `ledger_precheck.py "mmvf short row float mat-vec kernel warp per row"` -> receipts found:
- `rdna4-kernel-census/` (narrow matmul on RDNA4): a different kernel and a different architecture.
- **Upstream PR search:** #29633 (open) and #28875 (closed) change which matmuls are *routed* to `mmvf`, not its
  launch shape. #29633 sends more thin F16/BF16 matmuls into this kernel, which raises the stakes.
- **The precedent is inside the code:** MMVQ (the quantized kernel, the 23 us one) gained a `small_k` path in upstream
  #20635 (2026-03-22, "Increase number of output elements per-thread block if the K-dimension is small"). On generic
  NVIDIA it runs 4 warps per block with `rows_per_cuda_block = nwarps`, i.e. one row per warp. `mmvf` has no
  equivalent.
- **What this adds:** the same idea for the float kernel, measured on sm_60, with the mechanism separated (barriers vs
  residency).

## The change (`mmvf/mmvf_tune.patch`, buun `ab22bc538`)

- **One launch-shape change in `mul_mat_vec_f`:**
  - `row = blockIdx.x*blockDim.y + threadIdx.y`;
  - a `row >= nrows` early return (one new kernel argument);
  - `blockDim.y` rows per block, each row one warp, using the existing `block_size == warp_size` instantiation.
- **That instantiation already has no barriers or shared-memory reduction.** All of them sit behind
  `if (block_size > warp_size)`, so a whole-warp early return cannot strand a barrier.
- **No new template instantiations.** Every type, accumulator, batch width, fusion and MUL_MAT_ID path is reused
  unchanged.
- **Tuning only:** `GGML_MMVF_TUNE="R,KMAX"` sends rows with `ncols <= KMAX` to this path, R rows per block. Unset,
  the kernel is the original (row = blockIdx.x, one row per block). The env var is removed before phase B.
- **FP16 accumulation note:** F16 at the default precision accumulates in half2. With one warp per row, each thread
  sums `k/64` products. That is up to 16 at k=1024, against 8 at k=4096 and 28 at k=14336 on the current path. The
  chain stays inside what long rows already do as long as KMAX <= ~1792.

## Instrument

- **Host:** .73, P100 `CUDA0` only, 150 W, 1328 MHz (read back per leg). That is not the 1063 MHz of `RESULT_HC_Q8`,
  so all comparisons are A/B within .73; absolute us are not compared to 09-29.
- **Binaries:** static `test-backend-ops` (`BUILD_SHARED_LIBS=OFF`, sm_60, gcc-13 host, NCCL off) from a clean archive
  of `ab22bc538`, with `mmvf/mmvf_eval_cases.inc` and `mmvf/mmvf_perf_cases.inc` included.
  - **`tbo-base`:** unpatched.
  - **`tbo-tune`:** the tuning patch, incremental rebuild.
  - **`tbo-final`** (phase B): the selected rule hard-coded, env var removed.
- **Timing:** `test-backend-ops -m perf -b CUDA0 -o MUL_MAT`; us/run per case; 3 reps, arms interleaved within each
  rep; median of 3.
- **Contamination gate per leg:** before and after, no `llama-server` (`pgrep -x`), no compute apps on either GPU, and
  the SM clock read back. Mark sends traffic to the wake proxy rarely; .73 was woken by hand, so the proxy state is
  "suspended" and it will not start a server unless a request arrives. A contaminated leg is rerun and logged.
- **Correctness:** `test-backend-ops -m test -b CUDA0 -o MUL_MAT,MUL_MAT_ID,MUL_MAT_VEC_FUSION`, against the CPU
  backend. It includes the stock suite plus 192 added cases:
  - row counts 7 / 1001 / 10241 (not divisible by any R);
  - n = 1..8;
  - k = 64-1024;
  - a strided k view and bs/nr broadcast;
  - MUL_MAT_ID with and without broadcast b;
  - gate+bias fusion, with and without ids.
  - **On sm_60 these route to `mmvf`** for F16/BF16 at n <= 8 and F32 at n <= 3; larger F32 batches go to cuBLAS and
    act as a control.

## Phase A: tuning (exploratory, no verdicts)

- **Grid:** F16, m=10240, k in {64, 128, 256, 320, 384, 512, 768, 1024, 1536, 2048}, n in {1, 4} (n=4 is the MTP
  verify width .73 serves).
- **Arms:**
  - `base` (`tbo-base`);
  - `unset` (`tbo-tune`, env unset: must equal base; checks the patch's own cost);
  - `R1` (block 32, one row per block: no barriers, but sm_60's 32-blocks-per-SM cap limits occupancy to 50 %);
  - `R2`, `R4`, `R8`;
  - all with KMAX=4096 (always engaged on the grid).
- **Correctness in phase A:** `tbo-base` and `tbo-tune` with `GGML_MMVF_TUNE=4,4096` (every row up to k=4096 takes the
  new path) must both pass.
- **Mechanism reading (descriptive):**
  - if `R1` takes most of the win, the cost was the barriers and the shared reduction;
  - if only R >= 2 wins, it was residency;
  - if nothing moves at k=320, the diagnosis is wrong or the shape never reaches `mul_mat_vec_f`. Then stop.

**Selection rule (registered now, applied mechanically by `analyze_mmvf.py`):**
1. **R\*** = the R in {1, 2, 4, 8} with the lowest sum of median times over the grid cells with k <= 512 (both n).
   Ties within 1 % go to the smaller R.
2. **KMAX\*** = the largest grid k such that, for every grid k' <= k and both n, `t(R*) <= 0.97 x t(base)`.
3. **If k=64 already fails, there is no KMAX\*:** the fix is not adopted, phase B does not run, and the receipt reports
   the null.
4. **The rule is gated on NVIDIA with warp size 32**, the only hardware tested. AMD keeps the existing launch.

## Phase B: confirmation (registered verdicts)

`tbo-final` vs `tbo-base`, 3 interleaved reps, on shapes never used for selection (`mmvf_perf_cases.inc`, "held-out"):

| shape | type | m | n | k |
|---|---|---:|---:|---:|
| hc_up | BF16 | 10240 | 1 | 320 |
| hc_up | F32 | 10240 | 1 | 320 |
| — | F16 | 32000 | 2 | 192 |
| — | F32 | 16384 | 1 | 96 |
| — | F16 | 4096 | 1 | 448 |
| — | BF16 | 8192 | 8 | 640 |
| — | BF16 | 2048 | 1 | 256 |
| control: long row | F16 | 4096 | 1 | 4096 |
| control: hc_down | BF16, F16 | 320 | 1 | 10240 |

**hc_down is a different problem:** 320 rows of 10,240 is too few blocks, not too short a row. It needs split-k, not
this fix, and is expected unchanged.

| # | claim | rule | confidence |
|---|---|---|---|
| B1 | **hc_up is at least 2x faster** in BF16 and in F32 | `t_final <= 0.50 x t_base`, each type | 0.6 |
| B2 | **every held-out shape with k <= KMAX\* gains** | `t_final <= 0.80 x t_base`, each shape | 0.7 |
| B3 | **nothing regresses** | every confirm-set shape (held-out, controls, the grid) `t_final <= 1.03 x t_base` | 0.8 |
| B4 | **correctness unchanged** | `tbo-final` passes every case `tbo-base` passes (MUL_MAT, MUL_MAT_ID, MUL_MAT_VEC_FUSION) | 0.9 |

**Registered now, run on .194 on a later day (needs the 47 GB model):**

| # | claim | rule | confidence |
|---|---|---|---|
| B5 | **GSQ-RCO IQ3_XXS decode recovers most of the HCQ8 gain without converting anything** | second-pass decode, embedding table pre-read, final vs base build: >= 1.07x (HCQ8 got 1.118x cached) | 0.6 |
| B6 | **...at no fidelity cost** | mean KLD(final vs base) on the `RESULT_HC_Q8` wikitext setup < 0.001 (HCQ8: 0.0153) | 0.8 |

**Basis for B5:**
- 96 hc_up calls per token (2 per layer x 48; `tables/gsq_base_iq3xxs.tsv`).
- At 1063 MHz, 82.2 us each. If the fix brings them to ~30 us, that saves ~5.0 ms of the 53.1 ms cached token
  (18.83 tok/s), about 1.10x.

## Not tested

- Volta and later, AMD (the rule is gated off there), and the 1660 Ti (sm_75).
- Prefill: batch > 8 goes to cuBLAS or MMF, not this kernel.
- hc_down's few-rows shape.

## Deviations

Any change after the first timed row gets a numbered Deviation here before the affected rows run.

- **Deviation 1 (harness only, before any timed row; 10-01 19:05).** Two launch defects, neither touching the kernel
  or the rule:
  - **The mode is positional.** This `test-backend-ops` takes `test` / `perf`, not `-m perf`. The first launch printed
    only usage text and exited 0 for every leg, so no rows exist from it. The runner now fails any leg whose output
    lacks `us/run` or `tests passed`.
  - **buun `ab22bc538`'s stock perf list aborts in its own constructor**, on a flash-attention case
    (`GGML_ASSERT(!(v_is_view_of_k && v_is_k_view))`, `test-backend-ops.cpp:9671`), before any case runs. Perf mode
    now returns right after `mmvf_perf_cases.inc` (`mmvf/mmvf_rebuild.sh`), so only the registered cases run (30
    shapes, all parsed in a smoke run). Eval mode is unchanged.
  - **Rebuilt binaries:** tbo-base `22ce0765…`, tbo-tune `1c8e7170…`.

- **Deviation 2 (after phase A, before any phase B row; 10-01 20:05).** Written down before phase B runs.
  - **The registered selection rule returned null.** That is phase A's registered outcome. R\* = 2 came from the
    registered argmin (sum 318.0 us vs R4 319.2, R8 322.8, R1 331.5). But no KMAX\* exists, because one cell failed
    the ">= 3 % gain in every cell from k=64" test: **k=64 at n=4, where every arm sits at the ~20 us harness floor**
    (R2 = 1.005x base). The rule confused "no gain possible" with "regression". From k=128 to k=2048, R2 runs at
    0.25-0.76x base at both n.
  - **Revised KMAX rule (post-hoc, chosen after seeing phase A):** the largest grid k <= 1792 (this prereg's own FP16
    note: a half2 chain of k/64 <= 28 products) such that no cell k' <= k regresses (R2 <= 1.03x base, both n) and k
    itself gains (<= 0.97x, both n). `analyze_mmvf.py:select_revised` applies it mechanically: **KMAX = 1536.** The
    registered `select()` is unchanged. **Phase B's held-out shapes, never used for selection, are the confirmation.**
  - **The patch is restructured; the tuning patch's runtime row index is not shipped.** With the env var unset, the
    tuning binary ran the old path 2-6 % slower than base in every rep. An alternating-order check (tune-first and
    base-first, 3 rounds each) reproduced it: +3.2-4.3 % at m=10240 / k=1536-2048, +1 % at hc_down, 0 % at
    m=4096 / k=4096. So it is real, not order bias. Register counts are identical (31-32), so it is instruction cost
    ahead of each block's first load. That cost alone would fail B3.
    - In `mmvf/mmvf_final.patch`, `rows_per_block` is a template parameter (default 1). The multi-row instantiation
      exists only beside `block_size == 32`, and the bounds check sits under `if constexpr (rows_per_block > 1)`.
    - **Gate before phase B timing:** the default-path SASS (F16, half and float accumulators, block sizes 160 and 256)
      must be identical between `tbo-base` and `tbo-final`, with function names stripped.
    - The final R2 grid timings are also compared with phase A's env-R2 medians, to confirm the shipped code is the
      code that was tuned.
  - **Phase B runs as registered otherwise** (same order, shapes, B1-B4 thresholds). KMAX is passed to the analysis
    explicitly: `analyze_mmvf.py B raw_B raw_A 1536`.
  - **Phase A raw:**
    - `raw_A/` is the clean run, 20/20 gates clean, with the proxy stopped.
    - `raw_A_aborted/`: the proxy started the 27B at 19:05:55 after a request, and the gate blocked every later leg.
      Then the proxy suspended .73 at 19:39, because its busy probe does not count `test-backend-ops`.
    - `raw_A_collided/`: on wake, the suspended runner resumed alongside a new one. Both were killed by PID, and none
      of their rows are used.
