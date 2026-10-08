# Pre-registration -- where Kaden's 2x comes from: per-kernel nsys profile of the .73 daily build vs Kaden's P100 fork

**2026-10-08, before any profile row.** `kmic-p100-73/RESULT_KMIC_VS_DAILY_73.md` (M1) measured Kaden's fork (K) at
**2.06x plain decode** (30.95 vs 15.03 t/s) and **1.83x prefill** (401.2 vs 219.5) over the daily build (D), with
identical flags on the same GGUF and cards. buun asked for a profile of both to see where the difference is. Mark:
"Well I suppose we could look further at the disparity between buun/kaden's p100 performance..."

**Prior art checked:** `ledger_precheck.py "P100 decode kernel profile mmvq matvec nsys tensor split cuda graphs
pascal"` -> receipts found:
- `sm60-types/RESULT_SM60_TYPES.md` (09-23): a per-type decode kernel table on sm_60 (one build, many quant types).
- `FAILURE_MODES.md` AFM-19: a CUDA-graphs hypothesis once got a null from an env var that was read nowhere.
- `kmic-p100-73` M1: the end-to-end gap this decomposes.

**What this adds:** a whole-graph, per-kernel A/B of two builds on the same file, flags and cards. It is the first
attribution of the 2.06x / 1.83x to kernels, communication and idle time.

## Facts checked in source before registering (not hypotheses)

- **CUDA graphs are off in both matched arms.**
  - D (`ggml-cuda.cu` ~8080 at `510cbbbfa`) disables graphs below Volta unless `GGML_CUDA_FORCE_GRAPHS` is set.
  - K (`ggml-cuda.cu` ~5466 at `e48e240a8`) enables them on Pascal only when `GGML_CUDA_GRAPHS_PRE_VOLTA` is
    non-zero. M1's MK0 cells did not set it. His HANDOFF's "now the default" refers to his launch script.
  - The trace verifies this per cell (P1), per AFM-19.
- **The cross-GPU reduction is built differently, but D does not use NCCL kernels.** D's build cache has
  `GGML_CUDA_NCCL=ON` and K's `OFF`. The smoke capture of D (orientation, before this file was committed) shows **no
  `nccl*` kernels**: its exchange is 8,704 `cudaMemcpyPeerAsync` calls, recorded only as HtoD/DtoH copies, i.e.
  staged through host memory, since peer access is off on this platform (`kmic-p100-73`'s IOMMU finding), plus
  `k_bin_bcast` adds. The comm prediction below is therefore about size, not mechanism.

## Instrument

- **Profiler:** Nsight Systems **2022.4.2**, extracted (not installed) to `~/tools/nsys-2022.4.2` on .73 from NVIDIA's
  CUDA repo.
  - The installed 2023.4.4 importer fails on llama.cpp traces too ("Wrong event order", segfault).
  - 2025.6.3 records no CUDA trace on Pascal (checked: "does not contain CUDA trace data").
  - 2022.4.2 is what Kaden used on his P100s. A smoke capture of D imported cleanly (122,378 kernels, both GPUs).
  - Flags: `--trace=cuda --sample=none --cpuctxsw=none`; exported to SQLite.
- **Node:** .73, both P100s, 150 W / 1,328 MHz recorded before each cell. The wake proxy is stopped and a busy lock held.
- **Binaries:**
  - D: `/mnt/HDD/buun-510cb-nohost/build_sm60/bin/llama-server` (buun `510cbbbfa` + `f08683ffa`).
  - K: `/mnt/HDD/kmic-p100/src/build-opt/bin/llama-server` (`e48e240a8` + the `<algorithm>` include).
  - No env vars on either, as in M1's MD0/MK0.
- **Model:** unsloth `Qwen3.8-27B-Q6_K.gguf`. Prompts are corpus slices from `split-prefill-73/raw/corpus_ids.json`,
  the same as M1/M2: 2k `[212992:215040]`, 32k `[131072:163840]`.

## Cells (one profiled server each, in this order)

| cell | build | flags |
|---|---|---|
| PD16 | D | M1's exactly: `-ngl 99 -sm tensor -fa on -ctk f16 -ctv f16 -c 8192 -np 1 -b 2048 -ub 2048 -fit off` |
| PK16 | K | same |
| PDQ4 | D | same but `-ctk q4_0 -ctv q4_0 -c 34816` |
| PKQ4 | K | same as PDQ4 |

**Requests** (`/completion`, raw token ids, `cache_prompt: false`, `ignore_eos`, `n_predict` 256, temperature 0,
top-k 1), after a 16-token warmup:
- f16 cells: the 2k slice twice (`r1`, `r2`). `r2` is the measured one; `r1` is reported too.
- q4_0 cells: 2k, then 32k.

The q4_0 cells are the depth leg. D's `launch_fattn` converts the whole quantized cache to f16 on every call (see
`kmic-p100-fork` notes), and K removed that. f16 KV in the matched cells has nothing to convert.

## Analysis (`analyze_prof.py`, fixed before any row)

- **Windows:** each request's kernels form a cluster separated by more than 1 s of GPU idle.
  - With `t_end` = the cluster's last kernel end, the decode window is `[t_end - predicted_ms, t_end]`.
  - The prefill window is the `prompt_ms` before that, using the server's own timings.
- **Per window, per GPU:**
  - kernel time by name;
  - busy fraction (union of kernel intervals over the window);
  - memcpy time by kind (`copyKind` 1 HtoD, 2 DtoH, 8 DtoD, 10 PtoP). Copies run on the copy engines and can overlap
    kernels, so they are reported beside busy time, not added to it;
  - CUDA graph launches (from the runtime API table).
- **Categories:**
  - **matvec:** `mul_mat_vec*`, `quantize_q8_1`, any `mmv*`;
  - **matmul:** `mul_mat_q*`, `*gemm*`, `quantize_mmq*`;
  - **attention:** `flash_attn*`, `*fattn*`, `soft_max*`;
  - **gdn:** `gated_delta*`, `conv_state*`, `ssm*`;
  - **comm:** `nccl*`, plus PtoP/DtoH/HtoD memcpy inside the window;
  - **convert:** `convert*`, `cpy*`, `dequantize*`;
  - **elementwise:** everything else.
- **Reported per cell:** ms per decode token (`window / predicted_n`) by category, summed over both GPUs and per GPU;
  the D minus K difference by category; the top 15 kernels.

## Validity checks (a failure voids the affected rows; reported, not patched)

- **V1:** decode t/s under nsys is within 10 % of M1's unprofiled figures (D 15.03, K 30.95) in the f16 cells.
- **V2:** the decode window contains no matmul-category kernels (window alignment).
- **V3:** both GPUs have kernels in every window.
- **V4:** 150 W / 1,328 MHz before each cell.

## Predictions

| # | claim | conf. |
|---|---|---|
| P1 | No CUDA graph launches in PD16 or PK16 (manipulation check) | 0.9 |
| P2 | Decode, f16, 2k: the matvec category is >= 60 % of the D minus K difference in ms per token | 0.55 |
| P3 | Decode, f16: the comm category's D minus K difference is < 20 % of the total D minus K difference (both stage through the host) | 0.6 |
| P4 | Decode, f16: D's busy fraction is >= K's (the gap is kernel time, not idle) | 0.6 |
| P5 | Prefill, f16, 2k: the matmul category is >= 60 % of the D minus K prefill-window difference | 0.6 |
| P6 | Depth (q4_0): from 2k to 32k, D's attention+convert ms per decode token grows by >= 2x K's growth | 0.6 |
| P7 | The f16 2k greedy text is byte-identical between D and K (as in M1) | 0.85 |

## Not tested

- The served configs (VBR, MTP, `-np 2`, sampled drafts).
- Quality (KLD).
- Speed claims: per-kernel times under a profiler are attribution, not benchmarks, and V1 bounds the overhead.
- Determinism (the next leg).

## Deviations

Any change after the first profile row gets a numbered Deviation here before the affected rows run.
