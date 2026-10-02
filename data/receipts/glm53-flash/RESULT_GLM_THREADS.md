# Result -- GLM-5.3-Flash on .194: 20 physical-core threads is already the sweet spot (30 adds 1.8 %, 10 loses 18 %, 40 with SMT loses 29 %). mmap plus `--numa distribute` gives ~5.0 tok/s, 13 % above the 09-30 baseline.

**2026-10-02.** Pre-registration `PREREG_GLM_THREADS.md` (`0a6a936b`), no deviations. Runner `run_glm_threads.sh`,
probe `glm_probe.py`, analysis `analyze_glm_threads.py` (self-tested), output `RESULT_glm_threads.json`.

- **Raw:** `raw_threads/`.
- **Setup:** mainline `81ff93e`, UD-IQ3_XXS, auto-fit (identical VRAM in every arm), mmap, `--numa distribute`,
  `-c 16384 -np 1`, f16 KV, .194 at 150 W / 1063 MHz.

| threads | pass 1 | **pass 2 (median)** | vs t20 |
|---:|---:|---:|---:|
| 20 (first) | 1.26-3.30 (cold page cache) | **4.97** | |
| 10 | 4.07 | **4.06** | 0.82 |
| 30 | 4.89-5.11 | **5.07** | 1.02 |
| 40 (SMT) | 3.29-3.62 | **3.56** | 0.71 |
| 20 (repeat) | 4.93-4.97 | **4.98** | drift 1.001 |

| # | claim | result |
|---|---|---|
| T1 | a better thread count exists (>= 1.10x) | **does not hold.** Best is 30 threads at 1.018x |
| T2 | SMT does not help | **holds.** 40 threads = 0.71x |
| T3 | it scales with cores below 20 | **holds.** 10 threads = 0.82x |

## What it means

- **The thread lever is spent.** The CPU-expert path scales with physical cores up to the 20 the box has. SMT hurts
  badly, probably because sibling threads contend for the same AVX2 units and the per-layer barriers then wait on the
  slowest.
- **Best measured GLM-5.3 config on .194:** mmap + `--numa distribute`, 20-30 threads: **~5.0 tok/s**, against 4.39
  on 09-30's defaults (+13 %), the same size as DS4's +13.6 % from `distribute` (08-02).
- **Post-hoc, not registered:** `distribute` with `-lm none` (`RESULT_GLM_NUMA.md`, D) gave 4.68, against 4.97 here
  with mmap. Placement had no effect there, so the 6 % gap is the load mode or run-to-run variation. It was not
  separated.
- **The first arm's pass 1 is the page-cache cost:** 1.26 tok/s on the first request after the Flash-Next run
  evicted GLM's file pages.

## Not established

- Thread counts between 20 and 30, `-tb` separate from `-t`, and `--numa isolate`.
- Anything that changes the CPU work itself: `-ot` placement, a CPU-friendlier quant for the CPU experts, buun's
  EXL3 CPU kernels (N15).
