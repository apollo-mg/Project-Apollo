# Result -- where Kaden's 2x comes from: 94 % of the decode gap is one kernel (`mul_mat_vec_q`, same name, same Q6_K weights, 2.4x faster on K); 70 % of the prefill gap is D's fp32 SGEMM against K's fp16-product/fp32-fold GEMM; at depth, D's q4_0 decode attention (`flash_attn_ext_vec`) is 5.5x K's `flash_attn_ext_q4p`, and no cache conversion runs in decode

**2026-10-08.** Pre-registration `PREREG_KD_PROFILE_73.md` (`981d040c`, 19:46:19; first profile row 19:46:19), no
deviations.
- **Runner:** `run_prof73.sh` + `client_prof.py` on .73; `analyze_prof.py` (all committed with the prereg).
- **Raw:** `raw/` holds per-cell request records (`*.jsonl`, with generated text), analysis summaries (`*.summary.json`),
  commands, pre-cell clocks and nsys logs. The four SQLite exports (305-354 MB each) stay on .73 at `~/kdprof/`.
- **Profiler:** Nsight Systems 2022.4.2 (`--trace=cuda --sample=none --cpuctxsw=none`), extracted to `~/tools` on .73.
  The installed 2023.4.4 cannot import llama.cpp traces here, and 2025.6.3 records no CUDA trace on Pascal.

D = the .73 daily build (buun `510cbbbfa` + `f08683ffa`). K = Kaden's P100 fork (`e48e240a8`). Same Q6_K GGUF, same
2x P100, same flags (M1's: `-sm tensor -fa on -b 2048 -ub 2048 -np 1 -fit off`), no env vars.

## Validity

| check | result |
|---|---|
| **V1** profiler overhead (f16 cells, within 10 % of M1) | D: decode 14.32 (-4.7 %), prefill 218.8 (-0.3 %): **pass**. K: prefill 407.5 (+1.6 %): pass; **decode 27.68 (-10.6 %): fails** by 0.6 points |
| **V2** no matmul kernels in any decode window | **pass** (0 in all six) |
| **V3** both GPUs in every window | **pass** |
| **V4** clocks | **pass**: 150 W and 1,328 MHz on both GPUs before every cell |

- **V1's failure voids K's f16 decode rows for scoring**, as registered, so P2-P4 are scored void below.
- **The gap itself is not distorted.** The tracer costs both builds about 3-4 ms per token: D's window is 69.6 ms
  against 66.5 unprofiled, K's 36.0 against 32.3. So the profiled D-minus-K gap, **33.7 ms per token, matches M1's
  unprofiled 34.2 ms**. The decomposition below is therefore reported as observed, labelled unregistered where it
  rests on K's f16 decode.

## Decode, f16 KV, 2k context (request `r2`; `r1` agrees within 0.3 %)

ms per token, per GPU. The two GPUs run in parallel under tensor split, so per-GPU time is comparable with wall time.

| | D | K | D minus K | share of gap |
|---|---:|---:|---:|---:|
| wall per token | 69.58 | 35.99 | **33.59** | |
| matvec (`mul_mat_vec_q`, `quantize_q8_1`, `mul_mat_vec_f`) | 55.68 | 24.00 | **31.68** | **94.3 %** |
| GPU idle | 9.01 | 7.47 | 1.54 | 4.6 % |
| attention | 0.77 | 0.49 | 0.28 | 0.8 % |
| elementwise / norms | 3.27 | 3.10 | 0.17 | 0.5 % |
| GDN | 0.85 | 0.72 | 0.13 | 0.4 % |
| convert | 0 | 0.22 | -0.22 | -0.6 % |

- **One kernel:** `mul_mat_vec_q` is **107.6 ms per token on D against 45.2 on K** (both GPUs summed), over the same
  Q6_K weights.
- **Same template, different kernel** (from the trace's `demangledName` and launch records): both run
  `mul_mat_vec_q<Q6_K, ncols 1>`, but the bodies and launch shapes differ:

  | | block | rows per block | registers | shared memory | 8,704 x 5,120 call |
  |---|---|---:|---:|---:|---:|
  | D | 32 x 4 | 1 | 40 | 384 B | **187 us** (~195 GB/s) |
  | K | 32 x 2 | 2 | 80 | 6,048 B | **75 us** (~490 GB/s) |

  The P100's HBM2 peak is 732 GB/s. The difference is his kernel design, not a code path the carve-out switches.
- **What his OPTLOG says won on this path** (single column, Pascal):
  - Q6_K vec-dot at `vdr = 4`, with index math shared across the group (attempts 10-11; 29 % fewer load/store ops per
    block);
  - weights staged into shared memory in `uint4` units (attempt 12);
  - the scale and the int-to-float conversion folded out of the vdr loop (attempt 18; Pascal has no IMAD);
  - a q8_1 activation-quantization cache (attempt 36), which matches D's `quantize_q8_1` 2.5 vs K's 1.6 ms per token;
  - cooperative staging of the q8_1 activation, gated to one column on Pascal (attempt 42).
- **Communication is not the gap.** Both builds stage the tensor-split exchange through host memory: about 1.18 ms
  HtoD + 0.98 ms DtoH of copies per token on each, within 2 %. D has no NCCL kernels despite `GGML_CUDA_NCCL=ON`.
- **Launch count:** D issues 3,546 kernels per token across both GPUs, K 3,229. K fuses add + RMS norm
  (`add_rms_norm_mul_f32`).
- **D's GPUs are busier** (87 % against 79 %): the gap is kernel time, not idle.
- **No CUDA graph launches in any cell** (`cudaGraphLaunch` count 0), as the source check said.

## Prefill, f16 KV, 2k prompt

µs per prompt token, per GPU.

| | D | K | D minus K | share |
|---|---:|---:|---:|---:|
| wall per token | 4,570 | 2,454 | **2,116** | |
| matmul | 3,181 | 1,704 | **1,477** | **69.8 %** |
| GPU idle | 969 | 503 | 466 | 22.0 % |
| GDN | 168 | 9.5 | 159 | 7.5 % |
| everything else | | | 14 | 0.7 % |

- **The GEMM path is the carve-out's cost.** D dequantizes Q6_K and runs cuBLAS fp32 `sgemm_128x128x8_NT_vec`
  (6,294 µs per token, both GPUs). K runs `gemm_fold_kernel_u2` (3,290), his fp16-product, fp32-fold GEMM, which is
  how he handles the sm_60 fp16 accumulation problem (our ggml issue #25593) instead of the carve-out.
- **GDN prefill:** D's `gated_delta_net_cuda` costs 322 µs per token against K's chunked `gdn2_main` at 75.

## Depth, q4_0 KV, decode at 2k and 32k

| | D 2k | D 32k | K 2k | K 32k |
|---|---:|---:|---:|---:|
| decode t/s (profiled) | 14.04 | 12.10 | 26.62 | 25.28 |
| wall ms per token | 70.96 | 82.32 (+11.36) | 37.43 | 39.41 (+1.98) |
| attention, ms per token (both GPUs) | 3.30 | **25.94** | 1.31 | **4.89** |
| convert, ms per token | 0 | 0 | 0.42 | 0.42 |

- **The depth cost is the attention kernel itself.** D's `flash_attn_ext_vec` on q4_0 takes 25.7 ms per token at 32k
  against K's `flash_attn_ext_q4p` at 4.6: 5.5x. Attention growth explains D's +11.4 ms (11.3 per GPU) and K's +2.0.
- **No cache conversion runs in D's decode.** The convert category is empty in both D decode windows.
  - The whole-cache f16 conversion in buun's `launch_fattn` is not what slows q4_0 decode at depth.
  - It may still matter for VBR, whose degraded tiers are materialized for attention. Untested here.
- **32k prefill attention:** D's `flash_attn_tile` is 1,414 µs per token (both GPUs) against K's
  `fa_fold_qk2` + `fa_fold_pv2` at 517.

## Registered verdicts

| # | claim | conf. | result |
|---|---|---|---|
| P1 | no CUDA graph launches in PD16 / PK16 | 0.9 | **holds** (0 / 0) |
| P2 | decode: matvec >= 60 % of the gap | 0.55 | **void (V1)**. Unregistered: 94.3 % |
| P3 | decode: comm difference < 20 % of the gap | 0.6 | **void (V1)**. Unregistered: copies within 2 %, no comm kernels |
| P4 | decode: D busy >= K busy | 0.6 | **void (V1)**. Unregistered: 87 % vs 79 % |
| P5 | prefill: matmul >= 60 % of the gap | 0.6 | **holds: 69.8 %** |
| P6 | depth: D's attention+convert growth >= 2x K's | 0.6 | **holds: 6.3x** (+22.6 vs +3.6 ms per token, both GPUs) |
| P7 | f16 2k greedy text identical D vs K | 0.85 | **holds** (1,041 characters, both requests). q4_0 2k also identical; q4_0 32k diverges at character 183 (different attention kernels) |

## What it means (for buun)

Ranked by what each would buy the daily driver:
1. **The sm_60 matvec, 94 % of the plain-decode gap.**
   - K's `mul_mat_vec_q` does the same work 2.4x faster.
   - Porting it is the single change that matters for decode. Our notes say it is a port into buun's 3,100-line
     `mmvq.cu`, not a cherry-pick.
2. **The prefill GEMM, 70 % of the prefill gap.**
   - The carve-out sends every prefill GEMM through fp32 SGEMM, which is the accuracy-safe path. The carve-out exists
     because of a measured KLD problem.
   - K's `gemm_fold_kernel_u2` uses fp16 products with fp32 folds. His "~100x closer to fp64" figure is a simulated
     matvec on synthetic data against the q8_1 path, not a measurement of the fold GEMM against fp32 SGEMM.
   - So this is a **~1.8x prefill candidate that needs a KLD check against the carve-out build** before anyone adopts
     it.
3. **q4_0 decode attention at depth:** 5.5x at 32k. It matters for long contexts. The daily's VBR cache is a
   different attention path, so this needs its own check before it is claimed for the daily.
4. **Small items:** chunked GDN prefill (7.5 % of prefill), fused add + norm, about 9 % fewer launches.

Not changed by this: quality (no KLD panel), the served MTP path, and determinism (next leg).
