# Result -- GLM-5.3-Flash's 4.4 tok/s on .194 is not a NUMA problem: its 57 GB of CPU-resident experts decode at the same speed on one socket, the other, or interleaved 50/50. Only thread pinning helps (+6.7 %). The CPU side moves ~7 GB/s, far below one socket's 22.7 GB/s, so it is compute- or sync-bound.

**2026-10-02.** Pre-registration `PREREG_GLM_NUMA.md` (`95f94d91`), with Deviation 1 (`-lm none` in place of the
`--no-mmap` this mainline rejects; before any affected row). Runner `run_glm_numa.sh`, probe `glm_probe.py`,
analysis `analyze_glm_numa.py` (self-tested), output `RESULT_glm_numa.json`.

- **Raw:** `raw_numa/` (rows, per-arm `numastat -p` + `numa_maps` totals, server logs).
- **Host and build:** .194, 4x P100 at 150 W / 1063 MHz, mainline `81ff93e`.
- **Model and placement:** unsloth GLM-5.3-Flash UD-IQ3_XXS (09-30 files). Auto-fit put 12.2-13.9 GB of weights per
  GPU, identical in every arm; the rest of the experts are on the CPU. `-c 16384 -np 1`, f16 KV, `n_threads = 20`.
- **The page cache was dropped before every arm.** 8 of 288 experts are active per token.

## Results (median of 3 pass-2 requests, 256 tokens, `reasoning_effort` low)

| arm | expert memory node 0 / node 1 | pass 1 | **pass 2** |
|---|---|---:|---:|
| M: mmap (09-30 config) | 10.5 / 50.4 GB (17 / 83 %) | 4.40 | **4.39** |
| B1: `-lm none`, first touch | 58.6 / 0.03 GB (**99.9 / 0.1 %**) | 4.39 | **4.40** |
| D: `-lm none --numa distribute` | 13.9 / 44.5 GB (24 / 76 %) | 4.66 | **4.68** |
| I: `numactl --interleave=all`, `-lm none --numa numactl` | 29.3 / 29.3 GB (**50 / 50 %**) | 4.21 | **4.36** |
| B2: B1 repeated (drift check) | 13.9 / 44.4 GB (24 / 76 %) | 4.36 | **4.37** |

**Drift:** B2 / B1 = 0.994.

| # | claim | result |
|---|---|---|
| G1 | interleaving the expert memory speeds decode (>= 1.15x B) | **does not hold.** 0.99x (4.36 vs 4.39) |
| G2 | without a policy the experts pile onto one node (>= 70 %) | **holds.** B1: 99.9 % on node 0. (B2, the same config, landed 76 % on node 1) |
| G3 | distribute >= 1.05x B, and interleave >= distribute | **does not hold.** Distribute is 1.067x, but interleave is below it |

## What it means

- **Memory placement does not matter for this model.** Three placements (100 % on node 0, 76 % on node 1, exactly
  50/50) decode within 1 % of each other. First touch even chose different sockets in two identical runs (B1, B2)
  with no speed change.
- **The CPU side is not bandwidth-bound.**
  - Per token, 8 of 288 experts in ~57 GB of CPU-resident weights is ~1.6 GB, or ~7 GB/s at 4.4 tok/s. Node-local
    bandwidth on this box is 22.7 GB/s per socket (memory `numa-distribute-is-threads-only`).
  - The bottleneck is CPU compute (IQ3_XXS grid-lookup dot products on Haswell AVX2), thread synchronisation across
    43 expert layers per token, or the GPU/CPU hand-offs, not DRAM.
  - This contradicts that memory's "decode becomes host-bandwidth-bound" for this model and quant. The Flash-Next
    spill-ladder regimes it was written for were not retested.
- **Thread pinning is worth having:** `--numa distribute` gave +6.7 %, the same direction as DS4's +13.6 % (08-02).
  True interleave did not add to it, and its pass 1 was slower (4.21).
- **Levers for the EXL3 comparison (N15) that do not involve NUMA:**
  - put more experts on the GPUs with `-ot` (auto-fit left 1-2 GB per card unused);
  - a CPU-friendlier type for the CPU-resident experts (e.g. Q4_K instead of IQ3_XXS);
  - a thread-count sweep.
  - None of these was tested here.

## Not established

- Where the 227 ms per token actually goes (CPU expert compute vs GPU vs hand-offs). A per-op profile or
  `GGML_SCHED` timing would split it.
- Thread counts other than 20.
- Whether DS4's larger `distribute` gain (+13.6 %) came from its spill shape (`-ncmoe 40`) or its build.
