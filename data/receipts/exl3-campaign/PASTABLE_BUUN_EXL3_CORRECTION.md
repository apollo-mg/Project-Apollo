<!-- Follow-up draft for Mark, after the first note went out. Corrects two claims in it. Facts: buun's
     ggml/src/ggml-cuda/exl3.cu dispatch read 2026-09-13; kv-tensor-split/RESULT_EXL3_SM60_INFERENCE.md P-X6;
     exl3-campaign/RESULT_O11_CLEAN_BUILD.md; qwen4exp/RESULT_FLASHNEXT_RESIDENCY.md Amendment 4. -->

**Correction to my note above — two things I got wrong, and one now settled**

1. **"Every EXL3 path runs on the vector ALUs" is wrong.** That holds for the int8 path (≤ 8 rows,
   `sudot4` / `dp4a`). Past 8 rows — and for `GGML_EXL3_INT8=0` before Ampere — `ggml_cuda_mul_mat_exl3`
   reconstructs row chunks to fp16 and calls `cublasGemmEx(... CUBLAS_GEMM_DEFAULT_TENSOR_OP)`, which on gfx1201
   is hipBLAS and can land on the matrix cores. So they are reachable today, just behind a full fp16 reconstruct.
2. **"Mode 0 is untimed on our side" is also wrong.** We timed it during sm_60 qualification, at single-row
   decode: the int8 path was **2.9× faster** than reconstruct + cuBLAS (6.96 vs 2.43 t/s, 27B at 4.00bpw). What
   we have never timed is mode 0 **across row counts**, or anything on gfx1201.
3. **Item 3 is settled: with `GGML_CUDA_ALLREDUCE=internal`, all 15 of those tests pass.** So sm_60 is **34 of
   35**, and the only real failure is the `test-exl3-cpu-cache` assert in item 2. Having the NCCL-dependent tests
   skip when NCCL cannot initialise would still save the next person the same confusion.

**What that changes about the ask.** Before a new kernel: `MAX_M = 8` is the same on every arch. If reconstruct +
hipBLAS overtakes the int8 path below 8 rows on gfx1201 — plausible, since int8 already costs 3.15× at 4 rows
there — a **per-arch crossover** would put MTP verifies on the matrix cores with no new code. The int8 WMMA path
is still the better end state, since it skips the reconstruct, but the threshold is measurable first and I am
happy to run that sweep.

**One more, from running Flash-Next EXL3 on four P100s today.** The safetensors loader prepares streamable
tensors into a temp file — `prepare_file()`, into `$LLAMA_CACHE` if set, otherwise **the model directory**.
Flash-Next's n-gram table is 31 GB, so loading it onto a disk with 17 GB free died five minutes in with
`write error: No space left on device` — after the snapshot had already been verified. A free-space pre-check,
or a line in the docs, would save that trip. With room it loads fine: **50 GB across four cards, 18.4 t/s decode
at 3.05bpw, 11.7 minutes to load.**
