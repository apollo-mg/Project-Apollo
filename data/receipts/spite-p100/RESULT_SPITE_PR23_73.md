# Result -- Spite PR #23 runs Qwen3.8-27B Q6_K on two PCIe P100s: the layer split and cross-device switching work, the sm_60 kernels pass verify.py, and the greedy output matches llama.cpp up to a near tie; decode is 6.69 tok/s (0.75x llama.cpp `-sm layer`). Two defects found: MTP crashes on the split (illegal memory access), and `spite run` hard-codes a compounding repetition penalty

**2026-10-06.** Pre-registration `PREREG_SPITE_PR23_73.md` (`c9fd9a7e`), with Deviations 1-3, each registered
before its rows.
- **Runner:** `kit/run_tests.sh`.
- **Raw:** `raw/`, including run outputs, verify logs, bench JSON, llama.cpp JSON and the desktop `cargo test` log.

## Setup

- **Spite:** `giveen/spite` PR #23 head `ab8177a` (main `453e98f`).
  - Kernels `SPITE_MODELS=qwen/qwen3_5`, `SPITE_GPU_ARCHS=TESLA_P100`, CUDA 12.4.131 with gcc-13.4 as host, Release.
  - Rust 1.97.1 on .73.
- **Host:** .73, 2x Tesla P100-PCIE-16GB, PHB, no NVLink.
  - Driver 580.178.04.
  - SM clock locked at 1,328 MHz (`gpu_state_*.csv`), 150 W cap.
  - i7-8600K, 16 GB RAM.
- **Model:** unsloth Qwen3.8-27B Q6_K, 22,884,408,288 B, sha256 `562fbf76…486727`. `qwen35`, 64 blocks + 1 NextN.
- **llama.cpp reference:** buun `510cb-nohost`, `-sm layer -fa on -ctk f16 -ctv f16 -c 8192 -np 1`, no drafter.
- **Node state:** the daily driver and the wake proxy were down for the runs (15:29-15:49 and ~15:57-16:00) and were
  restored after each window.

## Results

| test | result |
|---|---|
| **T1, build** | **holds.** The vendor kernel `libkernel_qwen_qwen3_5_nvidia.so` has 3 sm_60 cubins; the card `.so` has 1. `cargo build --release` OK. |
| **T2, `cargo test --workspace`** | **holds** on the desktop (Deviation 2): 126 passed, 0 failed. On .73 it cannot build `openssl-sys`, because there are no OpenSSL headers. |
| **T3, load and split** | **The split works; one of the three answers is missing.** Every one of the 12 runs printed two stages: GPU 0 layers 0..33 (10.14 GiB), GPU 1 layers 33..64 (10.87 GiB). The total is weights 20.33 GiB + KV 0.53 GiB + recurrent state 0.15 GiB; load takes 21.5 s. Answers: " Paris.", and a correct one-sentence definition of photosynthesis. **"17 x 23" produced no tokens at all:** the first pick was `<|im_end|>`. T5b shows this is the sampler (below). |
| **T4, cross-device** | **holds.** With the stage order reversed (`--gpus 1,0`, so GPU 1 runs layers 0..33), and on a repeat, the generated text is byte-identical on all 4 prompts. The only differences are the GPU numbers in the stage lines. (The runner's whole-file `cmp` flagged those lines as DIFF; the generated text was checked separately.) Timing changes by under 1 %. |
| **T5, agreement (PR binary)** | **does not hold, and it is confounded.** Against llama.cpp greedy: p1 diverges at token 1 (`<|im_end|>` vs " 391"), p3 at "water," vs "water.", p4 at "water," vs "water and". p2 matches. Each divergence is a token that already occurs in the prompt. |
| **T5b, agreement with the penalty at 1.0** (Deviation 3) | **p1-p3 identical to llama.cpp up to llama.cpp's end-of-generation token:** " 391", "\n\nParis.", and the whole 23-token photosynthesis sentence. **p4 is identical for 15 tokens**, then " the" (Spite) vs " his" (llama.cpp). That misses the registered 16 by one. On the daily-driver server that position is a near tie: " his" logprob -0.9709 (p 0.379) against " the" -0.9818 (p 0.375). |
| **T6, verify.py** | **passes on sm_60.** Vendor kernel: 93 OK, 12 SKIP (ops the kernel does not provide: plain `attention`, some `linear_attn` geometries), 0 FAIL. That includes matmul across 28 types x 2 shapes (56 OK), and `attention_ex` with Q4_K/Q5_K/Q6_K weights (max abs diff 2.2e-6). The card `.so` passes too; it exports only NVLink helpers, so everything SKIPs. |
| **T7, speed** | **Spite `spite-bench`** (defaults: 8-token prompt "Benchmark prompt for throughput measurement.", 512 tokens, 5 runs): **decode 6.69 tok/s**, prefill 6.86 tok/s, TTFT 1,021 ms, peak 20,969 MiB. **llama.cpp, same prompt, 512 tokens (`ignore_eos`), 3 timed: 8.90 tok/s** (8.91, 8.90, 8.90). **Ratio 0.75.** `spite run` reports 6.7-6.9 tok/s, with prompt and generated tokens counted together. |
| **T8, MTP** | **`spite-bench --mtp` crashes on the split:** `cudaMemcpy H2D: an illegal memory access was encountered (700)`, right after placing the stages (GPU 0 10,255 MiB, GPU 1 10,987 MiB). `spite run --mtp` prints "features : mtp" but gives the same text at the same speed (6.71 tok/s), so speculation does not appear to engage there. |

## Registered verdicts

| # | claim | result |
|---|---|---|
| P1 | T1 and T2 hold | **holds** (T2 on the desktop, Deviation 2) |
| P2 | T3 passes on two GPUs | **does not hold as registered:** 2 of 3 answers. The missing one is the sampler, not the GPU path (T5b). |
| P3 | T4 holds | **holds** |
| P4 | T5 holds | **does not hold.** T5 is confounded by the sampler; T5b misses by one token on p4, at a measured near tie. |
| P5 | T6 passes on sm_60 | **holds** |
| P6 | Spite decode at least 50 % of llama.cpp `-sm layer` | **holds:** 0.75x |

## What it means

- **The PR does what it claims on real P100s.**
  - The hybrid decoder splits across two physical GPUs over plain PCIe.
  - Cross-device switching works in both stage orders, with identical output.
  - The qwen3_5 CUDA kernel compiled for sm_60 passes Spite's own verify tool.
  - With the sampler neutralised, its greedy output is llama.cpp's, up to a near tie.
  - That covers the "real cross-device switching" item the PR lists as untested.
- **Defects to fix before merge,** in order of severity:
  1. **MTP on a split crashes** (`spite-bench --mtp`, illegal memory access). The MTP block sits on the last GPU per
     the PR, so a device or pointer mix-up in the NextN path is the likely place. Not localised here.
  2. **`spite run` is not greedy at temperature 0.** `Executor::generate` hard-codes `repetition_penalty: 1.1`, and
     `apply_repetition_penalty` applies it **once per occurrence** in the whole context, prompt included: a token seen
     k times is divided by 1.1^k. That deleted the answer to "17 x 23" (the leading space token is in the prompt), and
     it will push long generations off common tokens. Standard practice applies it once per distinct token, with no
     penalty at temperature 0.
  3. **Generation stops only at `<|im_end|>`.** Raw completions run past `<|endoftext|>` into an invented next turn,
     and the special tokens are printed.
- **Observations, not defects:**
  - Prefill runs at decode speed (6.86 tok/s).
  - The dispatch table routes `prefill`, `attention`, `layer` and `spec_verify` to the generic kernel. Long prompts
    will be slow: about 10 minutes for 4k tokens at this rate.
- **Speed:** 0.75x llama.cpp's pipeline split on the same cards, from kernels that have not been tuned for Pascal (the
  `.bench` is still a placeholder). The daily driver (tensor split + MTP) is faster still; that was not measured
  here.

## Not established

- The PR's 6-GPU target (two GPUs here).
- Q5_K_S (not on hand).
- Tensor parallelism (not wired).
- Contexts beyond the short prompts used here.
- The cause of the MTP crash.
- Whether `spite run --mtp` speculates at all.
- Agreement measured as KLD or PPL (`spite-perplexity` has no CUDA hybrid path).

## Reported

- **2026-10-06:** posted to the PR as Mark's agent, with his OK: https://github.com/giveen/spite/pull/23#issuecomment-6025504371.
- **Requested by the author:** "you are more than welcome to make agent notes on the PR".
- **The PR head moved before the post:** `b33e50f` (the greedy penalty is off at temperature 0) and `06e44a0` (NVLink/PCIe
  probe, Q6_K budget). The comment says those were not tested.

## Addendum R: rerun at PR head `06e44a0`

Registered as Addendum R (`73663bdb`), before any R row.
- **Raw:** `raw_r/` (with `build_r.log`), `raw/t2_cargo_test_desktop_06e44a0.log`.
- **Runner:** `kit/run_tests_r.sh`. Its T4 compares the generated text only.

| test | result at `06e44a0` |
|---|---|
| T1 build | holds: 4 sm_60 cubins across the two `.so` files |
| T2 `cargo test` (desktop) | **138 passed, 0 failed** (12 new tests) |
| T3 | **holds now:** all 3 answers correct, including " 391" for 17 x 23. Same 2-stage placement (0..33 / 33..64). |
| T4 | holds: generated text identical across default, `--gpus 1,0` and repeat, on all 4 prompts |
| T5 (PR binary, greedy) | **holds:** byte-identical to the penalty-1.0 diagnostic build on all 4 prompts. p1-p3 equal llama.cpp through end-of-generation; p4 is equal for 15 tokens, to the measured near tie. |
| T6 `verify.py` | PASSED, vendor 93 OK / 12 SKIP / 0 FAIL; card PASSED |
| T7 | decode **6.69 tok/s** (6.691 vs 6.687 at `ab8177a`), prefill 6.86, TTFT 1,021 ms, peak 20,969 MiB |
| T8 | `spite run --mtp`: same text and speed as without it (6.71 tok/s). **`spite-bench --mtp` still crashes**, now on the reverse copy: `cudaMemcpy D2H: an illegal memory access was encountered (700)`, after the same two stage lines. |

**Verdicts:**
- **R1** (T5 holds with the PR binary, equal to T5b): **holds**.
- **R2** (the MTP split crash remains): **holds**.
- **R3** (decode within 3 % of 6.69): **holds**.

**Still open at `06e44a0`:**
- the MTP crash on the split;
- `--mtp` having no effect in `spite run`;
- the per-occurrence penalty at temperature > 0;
- stopping only at `<|im_end|>`;
- prefill at decode speed.

**Reported:** the follow-up was posted with Mark's OK at
https://github.com/giveen/spite/pull/23#issuecomment-6025811147.

## Addendum R3: round 3 at PR head `f1cc494`

Registered as Addendum R3 (`257ba7d3`), before any R3 row.
- **Raw:** `raw_r3/`, `raw/t2_cargo_test_desktop_f1cc494.log`.
- **Runner:** `kit/run_tests_r3.sh`.
- **The "before" for prefill** is the saved `06e44a0` binaries and kernel `.so` files (`--kernels-dir`), run in the
  same session.

| test | result at `f1cc494` |
|---|---|
| T1 build | holds: 6 sm_60 cubins across the `.so` files |
| T2 `cargo test` (desktop) | **146 passed, 0 failed** |
| T6 `verify.py` | PASSED, 93 OK / 12 SKIP / 0 FAIL |
| T6 `verify_batch_cuda.py` (sm_60) | **PASSED:** ffn batch m=3 max abs diff 8.5e-8, matmul 8.2e-8, attention_ex and linear_attn batch **bit-identical** to sequential |
| T3/T4 | holds: correct answers, 2 stages, identical text across default / `--gpus 1,0` / repeat |
| Greedy vs `06e44a0` | **identical** on all 4 prompts, up to where `06e44a0` printed its first EOG token |
| EOG stop (#4) | **fixed:** p1 " 391" (4 tokens), p2 "\n\nParis." (3), p3 the 22-token sentence, each ending without the token printed |
| T8 `spite-bench --mtp` (#1) | **no longer crashes**, but **acceptance 0.0 %** over 5 runs x 512 tokens (`spec=mtp K=1`). Decode 6.65 tok/s, no gain. |
| T7 prefill, 512-token padded prompt, 3 runs | **before (`06e44a0`) 7.234 tok/s, TTFT 70.78 s; after (`f1cc494`) 7.235 tok/s, TTFT 70.77 s. Unchanged.** |
| T7 defaults (decode) | 6.67 tok/s (prefill 6.86 at 8 tokens, TTFT 1,021 ms, peak 20,969 MiB) |
| llama.cpp `-sm layer`, the same 512-token prompt | **117.5 tok/s** prompt processing (117.7, 117.4, 117.5) |

**Why prefill did not move: the batched path is switched off on any split.** `batch_capable()` in
`crates/spite-models/src/hybrid.rs` requires `self.layer_stage.iter().all(|&s| s == 0)`, i.e. a single stage.
- A 27B Q5/Q6 does not fit one 16 GB P100, so on this PR's own target the prompt always takes the per-token path.
- The kernels do advertise the capability: `spite_kernel_caps` is exported by both the vendor `.so` and the generic
  one, and the batch verifier passes on sm_60.
- The author's batched-prefill check was on a single GPU, which explains the difference.
- The doc comment above `batch_capable` ("the per-card CUDA kernels do not yet") is stale for qwen3_5/nvidia.

**Verdicts:**
- **Q1** (both verify tools pass): **holds**.
- **Q2** (prefill at least 3x): **does not hold**, 1.00x, because of the stage gate above.
- **Q3** (decode within 3 %): **holds**, 6.67.
- **Q4** (greedy unchanged up to EOG): **holds**.
- **Q5** (p1-p3 end at EOG): **holds**.
- **Q6** (`--mtp` bench completes): **holds**, but with 0 % acceptance, so MTP is still not functional on the split.

**Open after round 3:**
- MTP acceptance 0 % on the split;
- `--mtp` in `run` (#3, the author's next step);
- batched prefill on multi-stage splits;
- prefill gap: 7.2 vs 117.5 tok/s for llama.cpp at 512 tokens.

**Not tested:** the per-distinct-token penalty at temperature > 0 (#2 claims a fix) was not exercised. Only greedy runs
were made.

**Reported:** round 3 was posted with Mark's OK at
https://github.com/giveen/spite/pull/23#issuecomment-6028319572.

## Addendum R4: round 4 at PR head `f85a2a2` (cross-stage batched prefill, "real" MTP)

Registered as Addendum R4 (`f29e1ad0`), before any R4 row.
- **Raw:** `raw_r4/`, `raw/t2_cargo_test_desktop_f85a2a2.log`.
- **Runner:** `kit/run_tests_r4.sh`.
- **The "before"** is the saved `f1cc494` binaries and `.so` files. The kernel `.so` is byte-identical between the two
  heads, so every difference is in the host code.

| test | result at `f85a2a2` |
|---|---|
| T1 / T2 | builds (6 sm_60 cubins); `cargo test` **148 passed, 0 failed** |
| T6 | `verify.py` PASSED (93 OK / 12 SKIP / 0 FAIL); `verify_batch_cuda.py` PASSED |
| T3/T4 | greedy text **identical to `f1cc494`** on all 4 prompts, in both stage orders and on a repeat. Short-prompt `spite run` wall time drops, e.g. p1 2.85 s -> 2.42 s. |
| T7 prefill, 512-token prompt, 2-stage split | **7.24 -> 7.89 tok/s (1.09x)**; TTFT 70.7 -> 64.9 s. llama.cpp `-sm layer` on the same prompt, box and file: 117.5 (round 3). |
| T7 defaults | decode 6.69 tok/s (prefill 8.07 at 8 tokens, TTFT 868 ms against 1,021) |
| T8 `spite run --mtp` | **text identical to plain decode on all 4 prompts**, so greedy speculative decoding is exact. It is slower: p4 128 tokens 5.60 tok/s against 6.79 plain. |
| T8 `spite-bench --mtp` | acceptance **99.6 / 99.4 / 99.0 %** at K = 1 / 2 / 3; decode **6.26 / 6.12 / 6.05 tok/s**, against 6.67 plain |

**Why MTP is slower despite ~99 % acceptance:**
- `Executor::generate_speculative_from_logits` (`crates/spite-executor/src/lib.rs`) checks each draft against the
  current logits and then feeds the accepted draft through `decode_step(d)`, one token at a time.
- So every output token still costs one full trunk pass, plus the NextN head per draft. The verify is sequential,
  not batched.
- The speedup needs one trunk pass over `[tok, d1..dK]` (m = K + 1, which the new cross-stage `forward_batch` can
  carry), then rolling back the KV and the GDN recurrent state for any rejected tail.
- The ~99 % acceptance comes from spite-bench's fixed prompt, a greedy 512-token continuation that is probably
  repetitive. It is not an acceptance rate for real text.

**Verdicts:**
- **S1** (verify tools pass): **holds**.
- **S2** (prefill at least 3x): **does not hold**, 1.09x.
- **S3** (plain decode within 3 %): **holds**, 6.67-6.69.
- **S4** (greedy text unchanged): **holds**.
- **S5** (acceptance above 30 %, and `--mtp` text identical): **holds**.
- **S6** (MTP at least 1.2x): **does not hold**, 0.91-0.94x.

**Note for the author:** `ncu` and `nsys` are installed on this box (`/usr/bin`). That is the profiling the author
said further work would need.

**Reported:** round 4 was posted with Mark's OK at
https://github.com/giveen/spite/pull/23#issuecomment-6044406798.

## Addendum R5: round 5 at `caa2d72` (head `6e708fb`), the author's list; R5-b, the acceptance cross-check

Registered as Addendum R5 (`cd37cdaa`) and R5-b (`33e72b2e`), each before its rows.
- **Raw:** `raw_r5/` (profiler streams left on .73: one `.nsys-rep` and five `.qdstrm`).
- **Runners:** `kit/run_tests_r5.sh`, `kit/run_tests_r5b.sh`. The first launch of r5 failed (the script was not
  executable) and was relaunched.

| item | result |
|---|---|
| verify / `cargo test` | `verify.py` PASSED (93 OK), `verify_batch_cuda.py` PASSED, `cargo test --workspace` **149/149** (desktop) |
| rows | 512/32/3: **prefill 7.37 tok/s** (TTFT 69.5 s), decode 6.70. Defaults: decode 6.69, TTFT 922 ms. Prefill is **-6.6 %** against round 4's 7.89, beyond the author's 5 % line; this is the added draft pass per prompt token. |
| (a) scaling | TTFT 1.03 / 3.87 / 15.34 / 69.52 s at 8 / 32 / 128 / 512 prompt tokens: **~120-135 ms per token, flat**. A per-token cost, not per-prompt. |
| (b) nsys | One usable profile (512-token prefill plus 16 decode, at `caa2d72`). The other four streams failed in nsys 2023.4's importer ("Wrong event order"), with and without the osrt trace. The bench's warmup is a full prefill, so the profile holds 2 x 512 prefill tokens. Kernel time **140.7 s**, about equal to 2 x 69.6 s: **kernels own the wall time, not host gaps.** `gemv_batch_kernel<Q6_K>` **81.5 %** (704 calls, **163 ms each**), `gemv_row_kernel<Q6_K>` 12.7 % (11,274 x 1.58 ms), `gemv_batch_kernel<Q8_0>` 4.4 %, everything else < 1 % each. API: `cudaLaunchKernel` 119.5 s (avg 737 us, blocking on a full queue), `cudaMemcpy` 44.7 s (the 22.7 GB model upload 21.6 s). |
| (c) counters | **Not available on sm_60 here:** Nsight Compute 2024.1 says "Profiling is not supported on device 0/1"; `nvprof` gives "Internal profiling error 4211:27" with driver 580. |
| (d) GPU log, 512 run | SM 1,328 MHz, mem 715 MHz, power median **106 W** (cap 150, "SW Power Cap: Not Active"), utilization.gpu **100 %**, **utilization.memory 2 %** |
| (e) | nsys 2023.4.4, ncu 2024.1.1. `gemv_batch_kernel<Q6_K>` **99 registers per thread** (the Q5_K instance 40) |
| (f) acceptance, Roman Republic prompt, 128 tokens | spite `--mtp` K = 1 / 2 / 3: **100.0 / 98.8 / 100.0 %**. **llama.cpp (buun 510cb, same GGUF and NextN head, `--draft-max 1`): 58 / 69 = 84.1 %**, 14.8 tok/s (plain 8.90). Greedy text identical between spite and llama.cpp on this prompt. |
| CPU gate row | not run: `DenseWeights::load` dequantizes everything to F32 (~108 GB for the 27B), against 15 GiB of RAM |

**Reading:**
- **Prefill is bound by the batched Q6_K GEMV kernel itself.**
  - At about 91 GFLOP per FFN-shaped call, 163 ms is ~0.56 TFLOPS, ~6 % of FP32 peak.
  - The memory bus sits at 2 %, with 99 registers per thread.
  - So the kernel is compute- and latency-bound on repeated Q6_K dequantization (once per 4-column chunk, i.e.
    128 times per weight at 512 tokens) at low occupancy. It is not bandwidth-bound.
- **The real-text acceptance is still an artifact.** The same NextN weights on the same prompt accept 84 % in
  llama.cpp, and spite's chained K = 3 drafts never miss. That is consistent with drafts that track the trunk's own
  next prediction, not with a working head.

**Verdicts:**
- **V1** (verify and tests unchanged): **holds**.
- **V2** (prefill within 5 %): **does not hold**, -6.6 %.
- **V3** (TTFT(512) / TTFT(128) >= 3.5): **holds**, 4.53.
- **V4** (kernels below 50 % of wall): **does not hold**, about 100 %.
- **V5** (acceptance 40-90 %): **does not hold**, 100 %, an artifact.
- **R5-b1** (llama.cpp acceptance below 95 %): **holds**, 84.1 %.

**Reported:** round 5 was posted with Mark's OK at
https://github.com/giveen/spite/pull/23#issuecomment-6048055944.

## Addendum R6: round 6 (`2a7d5ac`) and the row-tiling commit (`69676bc`, PR head), one pass

Registered as Addendum R6 (`ac9f40c7`, 17:39), Deviation R6-1 (`5b8f6920`, 18:08) and R6-2 (`84963bf0`, 18:14), each
before its rows (first R6 row 17:40). The approximate times written inside the prereg are off by a few minutes; the
commit times are the record.
- **Raw:** `raw_r6/` (home paths redacted). **Runners:** `kit/run_tests_r6.sh`, `kit/run_tests_r6_1.sh`; R6-2 ran inline
  (its commands are in `raw_r6/run.log`'s R6-2 lines).
- **Small model (Mark: "pick whatever works and fits"):** unsloth `Qwen3.5-2B-MTP-GGUF` / `Qwen3.5-2B-Q6_K.gguf`,
  sha256 `0559d914...90e7af73` (matches the Hugging Face LFS oid). `qwen35`, 24 trunk blocks + 1 NextN; ~7.8 GB as F32.

**Checks:** `verify.py` PASSED (93 OK / 12 SKIP / 0 FAIL) and `verify_batch_cuda.py` PASSED on the `69676bc` sm_60 `.so`;
`cargo test --workspace` at `69676bc` (desktop) **150 passed, 0 failed**, 3 ignored.

**27B prefill, 512-token prompt, 32 tokens, 3 runs, 2-stage split:**

| binary | prefill tok/s | TTFT | decode tok/s |
|---|---:|---:|---:|
| `6e708fb` (R5 head, rerun) | 7.36 | 69.5 s | 6.69 |
| `2a7d5ac` | 9.63 (**1.31x**) | 53.2 s | 6.69 |
| `69676bc` | **18.54** (**1.93x** over `2a7d5ac`, 2.52x over R5) | 27.6 s | 6.67 |

- Defaults at `69676bc`: decode 6.69, TTFT 427 ms (R5: 922 ms).
- llama.cpp `-sm layer` on the same box: 117.5 tok/s prefill, so spite is at 0.16x.
- **Registers** (`cuobjdump -res-usage`, `gemv_batch_kernel<Q6_K>`): 75 at `2a7d5ac` (R5, chunk 4: 99); at `69676bc` 76 for
  (tile 1, chunk 8) and 128 for (tile 4, chunk 4). **No spills** (`LOCAL:0`) in any GEMV instance. The chunk sweep was
  not run (as registered): the 27B's large projections take the tiled form, where the chunk is fixed at 4.

**MTP, Roman Republic prompt, 128 tokens, greedy:**

| | K | acceptance | draft-vs-trunk TV | decode tok/s |
|---|---|---:|---:|---:|
| 27B split, `69676bc` | plain | | | 6.71 |
| | 1 / 2 / 3 | **100 / 100 / 100 %** | 0.098 / 0.110 / 0.126 | 10.03 / 11.51 / 12.39 |
| 27B split, `2a7d5ac` (R6-2) | 1 | 100 % | 0.098 (same digits) | 6.65 |
| 2B unsplit, `69676bc` | plain | | | 43.4 |
| | 1 / 2 / 3 | **82.9** / 29.0 / 53.3 % | 0.50 / 0.52 / 0.56 | 31.3 / 18.8 / 22.7 |
| llama.cpp (buun `510cb`), same 2B file, one GPU | 1 | **81.4 %** (57/70) | | 113.6 |

**Greedy text (`spite run`):**
- Plain at `69676bc` equals R4's on all 4 raw prompts. The 2B's plain text equals llama.cpp's greedy text over its full
  654 characters. 2B forced split (`--gpus 0,1 --layer-split 12,12`) plain equals unsplit plain.
- **`--mtp` differs from plain in every case tested:**
  - 27B at K = 3 and K = 1, at character 14 ("The last king, Tarquinius..." becomes "The last king of Rome..."; the K = 3 text
    later reads "overthrown in 5091509 BC");
  - 27B K = 1 at `2a7d5ac`, byte-identical to `69676bc`'s K = 1 text;
  - 2B unsplit at K = 3 and K = 1, at character 11, after which it repeats the prompt back;
  - 2B split, byte-identical to 2B unsplit `--mtp`.

**2B CPU gate row** (`--device cpu --n-prompt 16 --n-tokens 8 --n-runs 1`): prefill 0.25 tok/s, decode 0.16, TTFT
64.5 s. The same shape on sm_60: 131.8 / 44.8 tok/s, TTFT 121 ms. `peak_mem_mib` reads 1,563 on both, so it is probably
not measuring the CPU run.

**Verdicts:**
- **W1** holds. **W2** holds (1.31x). **W3** holds (1.93x). **W4** holds (6.67, -0.3 %). **W8** holds.
- **W5** fails: acceptance >= 95 % holds, but TV is 0.098, not < 0.05.
- **W6** holds as measured (1.50x at K = 1), but the speedup comes from accepting tokens the trunk would not emit, so it
  is not a usable speedup.
- **W7** fails: the 2B's head is healthy unsplit (82.9 % vs llama.cpp's 81.4 % on the same file).
- **W9** fails: plain holds, `--mtp` diverges.
- **R6-1a**, **R6-1b**, **R6-1c** and **R6-2a** hold.

**Reading:**
- **Prefill:** row tiling is the biggest single step so far, and larger on the P100 (1.93x end to end) than the
  author's RTX 5090 screen (1.42-1.58x per projection).
- **MTP greedy output is not exact,** on both models, split or not, at both heads. There are two symptoms:
  - **2B: the head is fine; the rollback is not.** On a rejected draft (greedy), `rollback_drafts(n > 0)` calls
    `restore_recurrent`, which puts back the GDN conv/delta state saved before the whole verify batch
    (`crates/spite-models/src/hybrid.rs`). The executor then advances `n_ctx_used` by `1 + accepted` and samples from
    `batch_logits[accepted]` (`crates/spite-executor/src/lib.rs`, batched path), and nothing re-runs the verified token
    and accepted drafts through the GDN layers. After the first rejection the recurrent state is missing `1 + accepted`
    tokens. This is from reading the code, not instrumented; it fits the divergence at character 11, the prompt
    regurgitation, and K = 2's 29 % sitting below K = 1's 83 %.
  - **27B: 100 % acceptance and still divergent.** With no rejections, no rollback runs, yet the verify rows agree with
    drafts that plain decode does not produce. It is not the row tiling (`2a7d5ac` gives the same text and the same
    TV digits) and not the split (the 2B's split and unsplit `--mtp` texts are identical). R4's sequential verify also
    gave 99-100 % on this model, with text equal to plain (exact by construction), so the 27B's near-perfect
    draft/trunk agreement predates the batched verify. Not localised.
- **On the 2B, MTP is slower than plain at every K** (31 / 19 / 23 against 43 tok/s), even at a healthy 83 %.

**Not run:** the author's Q5 (sending the R5 `.nsys-rep`/`.qdstrm` files) needs Mark's decision on what leaves the box.
