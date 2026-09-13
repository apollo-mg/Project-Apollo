<!-- Draft for Mark to rework and send; not posted anywhere. Kernel facts read at buun da458765d
     (ggml/src/ggml-cuda/exl3.cu, exl3-gemv.cuh, exl3-gemv-int8.cuh, mma.cuh); test-side facts from the
     c7f114d34 build and ctest run on .194, 2026-09-13. Row-scaling figures: RESULT_EXL3_MTP_SWEEP.md and
     RESULT_EXL3_RDNA4_MTP.md. Receipts: RESULT_O11_CLEAN_BUILD.md (addendum), BACKLOG S7. -->

**EXL3 kernel paths vs. arch — possibly worth a look** (read at `da458765d`)

Our EXL3 campaign pinned the MTP penalty on EXL3 almost entirely to multi-row cost: a 4-row verify batch
costs EXL3 **2.08×** a single row on P100 (GGUF 1.37×) and **3.15×** on the 9070 XT (GGUF 1.74×). I went
looking at why:

- `exl3_int8_applicable` takes the int8 path for **m ≤ 8** (`exl3_int8::MAX_M`), and the MoE variant only
  up to **2,048 token-expert pairs** (`EXL3_MOE_PAIRS_MAX`). Flash-Next at `-ub 512` is 512 × 10 =
  **5,120 pairs**, so its prefill never takes the int8 path.
- The only matrix-core code in the EXL3 kernels themselves is the inline PTX `mma.sync` GEMV at
  `exl3-gemv.cuh:21`, gated `!GGML_USE_HIP && __CUDA_ARCH__ >= 800`. So on RDNA4 and Pascal the int8 path
  (`sudot4` / `dp4a`) — which every batch of 8 rows or fewer takes by default, MTP verifies included — runs on
  the vector ALUs.
- Past 8 rows, and in `GGML_EXL3_INT8=0` before Ampere, it reconstructs row chunks to fp16 and calls
  `cublasGemmEx(... CUBLAS_GEMM_DEFAULT_TENSOR_OP)`. On gfx1201 that is hipBLAS, so the 9070's matrix cores are
  reachable today — but only after a full fp16 reconstruct of the weights.
- That fits the numbers: RDNA4 has the WMMA units and also the worst row penalty on the int8 path.

**Cheaper first step:** `MAX_M = 8` is the same on every arch. If reconstruct + hipBLAS overtakes the int8 path
below 8 rows on gfx1201 — plausible, since int8 already costs 3.15× at 4 rows there — a per-arch crossover would
move MTP verifies onto the matrix cores with no new kernel.

**The kernel idea:** an int8 WMMA path for RDNA3/4 multi-row batches (MTP verify, MoE expert batches). RDNA4's WMMA
takes IU8 as well as FP8, so it could keep today's int8 numerics, and `mma.cuh` already carries RDNA4
layouts — it might slot in through the existing tile abstraction rather than new asm. FP8 WMMA would also
work, but it changes the numerics.

Happy to measure either way: a row-scaling sweep (m = 1, 2, 4, 8, 9, 16 × `GGML_EXL3_INT8` unset / 0 / 2,
EXL3 against a matched GGUF) on gfx1201 and sm_60, or a branch if you try something. We timed mode 0 once, on sm_60 at single-row decode,
where it means reconstruct + cuBLAS: the int8 path was 2.9× faster (6.96 vs 2.43 t/s, 27B at 4.00bpw). It has
never been timed across row counts, or on gfx1201.

**Also, test-side, from building `c7f114d34` on 4× P100 (GCC 15.2):**
1. A full build fails at `tests/test-cache-plan-record.cpp:826` — ambiguous `operator==` between an
   `ordered_json` element and `nlohmann::json::array(...)`. Built explicit targets to get past it.
2. `test-exl3-cpu-cache` aborts on sm_60: `[moe-cache] CUDA0 skipped: compute capability 600 is below
   700`, then `GGML_ASSERT(session)` at `test-exl3-cpu.cpp:220`. Looks like it wants to return the skip
   code 77 there instead.
3. 12 multi-GPU shard/expert tests abort in `ggml_backend_cuda_comm_allreduce_nccl` when ctest runs bare. With
   `GGML_CUDA_ALLREDUCE=internal`, which we always set on the P100s, all 15 pass. Might be worth having them
   skip (77) when NCCL can't initialise, so a bare `ctest` on Pascal doesn't read as 12 failures.

With that set, 34 of 35 `ctest -R exl3` tests pass on sm_60 — the 35th is item 2. No EXL3 kernel test fails on Pascal.
