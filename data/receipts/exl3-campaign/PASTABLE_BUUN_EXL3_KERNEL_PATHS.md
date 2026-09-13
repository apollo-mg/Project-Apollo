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
- The only matrix-core code in the EXL3 kernels is the inline PTX `mma.sync` at `exl3-gemv.cuh:21`, gated
  `!GGML_USE_HIP && __CUDA_ARCH__ >= 800`. So on RDNA4 — and on Pascal, which has no matrix units — every
  EXL3 path, the int8 one (`sudot4` / `dp4a`) and `GGML_EXL3_INT8=0` alike, runs on the vector ALUs.
- That fits the numbers: RDNA4 has the WMMA units and also the worst row penalty.

**Idea:** an int8 WMMA path for RDNA3/4 multi-row batches (MTP verify, MoE expert batches). RDNA4's WMMA
takes IU8 as well as FP8, so it could keep today's int8 numerics, and `mma.cuh` already carries RDNA4
layouts — it might slot in through the existing tile abstraction rather than new asm. FP8 WMMA would also
work, but it changes the numerics.

Happy to measure either way: a row-scaling sweep (m = 1, 2, 4, 8, 9, 16 × `GGML_EXL3_INT8` unset / 0 / 2,
EXL3 against a matched GGUF) on gfx1201 and sm_60, or a branch if you try something. None of our EXL3
speed numbers so far set the mode, so mode 0 is untimed on our side.

**Also, test-side, from building `c7f114d34` on 4× P100 (GCC 15.2):**
1. A full build fails at `tests/test-cache-plan-record.cpp:826` — ambiguous `operator==` between an
   `ordered_json` element and `nlohmann::json::array(...)`. Built explicit targets to get past it.
2. `test-exl3-cpu-cache` aborts on sm_60: `[moe-cache] CUDA0 skipped: compute capability 600 is below
   700`, then `GGML_ASSERT(session)` at `test-exl3-cpu.cpp:220`. Looks like it wants to return the skip
   code 77 there instead.
3. (Our side, still checking.) 12 multi-GPU shard/expert tests abort in
   `ggml_backend_cuda_comm_allreduce_nccl` when ctest runs without `GGML_CUDA_ALLREDUCE=internal`, which we
   always set on the P100s. Re-running them with it after the current bench — will report back.

Everything else in `ctest -R exl3` passed on sm_60: 22 of 35.
