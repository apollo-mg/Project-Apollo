# Result -- one warp per row makes short float mat-vec faster on P100: hc_up 3.0x (BF16 66.7 -> 22.3 us) and 2.4x (F32), held-out shapes 1.8-3.3x, with the default path's SASS unchanged and every correctness case passing. The registered selection rule returned null on a floor cell; the cutoff was then chosen post-hoc (Deviation 2) and confirmed on held-out shapes. **On .194 (10-02) it speeds GSQ-RCO Flash-Next decode 1.113x (B5 holds). B6 (KLD < 0.001) fails at 0.0139, but the unpatched build's own prefill-vs-decode paths diverge by 0.0144: this model amplifies any numeric change to that floor.**

**2026-10-01.** Pre-registration `PREREG_MMVF_SHORTROW.md` (`074d0e1`), with Deviation 1 (harness only) and
Deviation 2 (post-hoc cutoff, restructured patch), both committed before the rows they affect. The patch is
`mmvf/mmvf_final.patch` against buun `ab22bc538` (rows per block 2, cutoff k <= 1536, NVIDIA with warp size 32
only). Analysis `mmvf/analyze_mmvf.py` (self-tested).

- **Raw:**
  - `mmvf/raw_A/` (tuning; `phaseA.json`);
  - `mmvf/raw_B/` (confirmation; `phaseB.json`);
  - `mmvf/order/` (order-bias check);
  - `mmvf/sass/` (default-path SASS, base vs final, plus the tuning binary as a positive control).
- **Host:** .73, one P100 (`CUDA0`), 150 W, 1328 MHz read back on every leg. The wake proxy was stopped during both
  phases. All 20 phase A gates and all 7 phase B gates were clean (no llama-server, no other compute process).
- **Binaries:** static `test-backend-ops`. tbo-base `22ce0765…`, tbo-tune `1c8e7170…`, tbo-final `83304070…`.

## Registered verdicts (phase B, held-out shapes, 3 reps)

| # | claim | result |
|---|---|---|
| B1 | hc_up >= 2x faster in BF16 and in F32 | **holds.** BF16 66.7 -> 22.3 us (**0.335x**); F32 65.0 -> 26.8 us (**0.413x**) |
| B2 | every held-out shape with k <= cutoff gains (<= 0.80x) | **holds.** all 7 at 0.30-0.56x |
| B3 | nothing regresses (<= 1.03x) | **holds.** worst 1.010x (k=64, n=4, the harness floor); the untouched path reads 1.000-1.002x |
| B4 | correctness unchanged | **holds.** 1253/1253 cases pass, the same as base (MUL_MAT, MUL_MAT_ID, MUL_MAT_VEC_FUSION for F16/BF16/F32, including 192 added short-row cases) |

**Phase A's registered selection rule returned null.**
- Rows per block came out as 2, by the registered argmin.
- No cutoff qualified. The rule required a >= 3 % gain in every cell from k=64 up, and k=64 at n=4 sits at the ~20 us
  harness floor for every arm (1.005x). That is a mis-specified rule, not a failed kernel.
- The cutoff k <= 1536 came from a post-hoc rule (Deviation 2): no regression up to k, a gain at k, and the
  prereg's own FP16 cap.
- B1-B4 ran on shapes never used for selection.

| held-out shape | base | final | ratio |
|---|---:|---:|---:|
| hc_up BF16, m=10240, k=320, n=1 | 66.7 us | 22.3 us | **0.335** |
| hc_up F32, m=10240, k=320, n=1 | 65.0 | 26.8 | **0.413** |
| F16, m=4096, k=448, n=1 | 38.1 | 11.4 | 0.299 |
| F16, m=32000, k=192, n=2 | 152.1 | 62.5 | 0.411 |
| BF16, m=2048, k=256, n=1 | 12.4 | 5.2 | 0.419 |
| BF16, m=8192, k=640, n=8 | 183.8 | 98.2 | 0.534 |
| F32, m=16384, k=96, n=1 | 43.9 | 24.6 | 0.560 |
| control: F16 m=4096, k=4096 | 80.9 | 80.9 | 1.000 |
| control: hc_down BF16 / F16 (m=320, k=10240) | 18.7 / 18.7 | 18.7 / 18.7 | 1.000 / 1.001 |

## What the tuning showed (phase A, F16, m=10240; ratio to base)

| k | base n=1 | R1 | R2 | base n=4 | R1 | R2 |
|---:|---:|---:|---:|---:|---:|---:|
| 64 | 19.7 us | 0.998 | 0.733 | 19.9 us | 1.028 | 1.005 |
| 128 | 28.5 | 0.699 | 0.560 | 49.6 | 0.459 | 0.456 |
| 320 | 66.5 | 0.333 | 0.335 | 118.3 | 0.295 | 0.299 |
| 512 | 101.4 | 0.255 | 0.252 | 188.6 | 0.270 | 0.270 |
| 1024 | 113.5 | 0.422 | 0.424 | 212.1 | 0.464 | 0.467 |
| 1536 | 128.6 | 0.540 | 0.547 | 246.7 | 0.589 | 0.596 |
| 2048 | 121.6 | 0.756 | 0.762 | 254.4 | 0.762 | 0.779 |

- **The cost was the block shape, not residency.** R1 is the existing kernel launched with 32 threads and one row
  per block: no barriers, no shared-memory reduction. It takes essentially the whole win from k=320 up (at k=256, n=1: 0.40 vs R2's 0.33).
  - Packing rows (R2-R8) helps only at k <= 128, where sm_60's cap of 32 resident blocks per SM leaves
    32-thread blocks at half occupancy.
  - R2, R4 and R8 are within 1.5 % of each other.
- **The default launch is suboptimal far beyond "short" rows on sm_60.**
  - One warp per row is still 0.42x at k=1024 and 0.76x at k=2048.
  - The block-size heuristic minimises loop iterations, not time: base k=512 (101 us) is slower than base k=768
    (88 us).
  - The shipped cutoff stops at 1536 only because of the FP16 cap (below), not because the gain ended.
- **The tuning patch's runtime row index cost the old path 3-4 %.** It was confirmed real by an alternating-order
  check: +3.2-4.3 % at m=10240 / k=1536-2048, 0 % at m=4096 / k=4096, identical register counts.
  - The final patch makes rows per block a template parameter.
  - **All 22 default-path instantiations checked have identical SASS** in tbo-base and tbo-final, with names and
    addresses stripped: F16 (half and float accumulators), BF16 and F32 at blocks 160/256 and n=1/4, plus F16 and
    BF16 fusion and BF16 multi-token-ID.
  - **Positive control:** the same probe sees 118 changed lines in the tuning binary.
  - The final R2 timings match phase A's tuned R2 within 0.005 on every grid cell.

## End to end on .194 (B5/B6, 10-02; Deviations 3-4)

**Setup:**
- Builds: base and final, both static from `ab22bc538`.
- Model: GSQ-RCO IQ3_XXS Flash-Next, 4x P100 at 150 W / 1063 MHz (read back).
- Raw: `mmvf/raw_b56/` (`RESULT_b56.json`, `decode.jsonl`, `kld_*.txt`, server logs, `run.log`).

| # | claim | result |
|---|---|---|
| B5 | decode >= 1.07x (pass 2, pooled per build, 4 fresh servers ABBA) | **holds. 1.113x**: 18.78 -> 20.90 tok/s (12 rows each). Per server, pass 2: base 18.78 / 18.78, final 20.90 / 20.90 |
| B6 | mean KLD(final vs base) < 0.001 at `-ub 1` | **does not hold. 0.0139 +/- 0.0006**, same top token 96.4 %. Exercised gate passed (final 42.4 vs base 47.2 ms/token, 0.90x); self-control 0.000000 |

- **The speedup is what the kernel timings predicted:** ~1.11x from 96 hc_up calls x the measured kernel ratio.
  - It equals the Q8_0 conversion's cached speed (1.118x), and leaves the BF16 weights unchanged.
  - Pass 1 is as fast as pass 2 (20.87 vs 20.90), because the embedding shard is pre-read.
- **Greedy text:** 3/6 prompts identical between builds. The others first differ at characters 20, 360 and 476, and
  read coherently on both sides. Each build is deterministic (6/6 identical across its two servers).
- **B6 failed as registered.** The 0.001 threshold was set without measuring this model's sensitivity.
  - **The post-hoc control C2 (Deviation 4, reading rule committed before it ran)** scored the **unpatched** build's
    own `-ub 512` (prefill kernels) against its `-ub 1` (decode kernels) logits: **mean KLD 0.0144**, median 0.0014,
    same top 96.4 %.
  - That is the same divergence as the patch (0.0139, median 0.0014, 96.4 %). By the fixed rule, the patch
    diverges no more than two legitimate code paths of the same build do.

    | comparison | mean KLD | median | p99 | same top | mean ln(PPL ratio) |
    |---|---:|---:|---:|---:|---:|
    | final vs base, both `-ub 1` (the patch) | 0.0139 | 0.0014 | 0.175 | 96.4 % | +0.0021 +/- 0.0031 |
    | base `-ub 512` vs base `-ub 1` (C2, no patch) | 0.0144 | 0.0014 | 0.194 | 96.4 % | +0.0049 +/- 0.0034 |
    | HCQ8 vs base, both `-ub 512` (09-29, weights converted) | 0.0153 | 0.0017 | 0.197 | 96.5 % | -0.0075 +/- 0.0034 |

  - **Hypothesis, not shown:** MMVQ quantises activations to q8_1 before each quantised matmul. So a ~1e-7 float
    difference can flip a rounding step, and that compounds through 48 layers and the recurrent state. That would
    give a floor that does not depend on how small the original difference was.
- **Consequence for HC_Q8 (09-29):** its "conversion costs KLD 0.015" may be largely this floor, not Q8_0 precision.
  That run had no path-noise control, so it cannot be separated after the fact. A forward note is added there.
- **The B5 servers were not `numactl`-bound** (FAILURE_MODES AFM-28). Two things make that harmless here: the four
  servers agreed to 0.01 tok/s, and the same day's NUMA test (`qwen4exp/split-conc/RESULT_NUMA_PREFILL.md`) found
  the socket irrelevant for layer-split decode.
- All three `llama-perplexity` runs through the runner exited 1 despite complete output; C2, run directly, exited 0.
  The gates read content, not exit codes.

## What it means

- **GSQ-RCO's BF16 hyper-connections no longer need converting.**
  - On .73's clock, the 96 hc_up calls per token drop from 66.7 to 22.3 us, about 4.3 ms per token.
  - At .194's 1063 MHz, the same ratio predicts ~5.3 ms of the 53.1 ms cached token, about 1.11x. That is the HCQ8
    speed (1.118x) at zero conversion cost. **Measured on .194: 1.113x** (B5).
- **A KLD threshold needs a path-noise control.** On this model any numeric change, even the same build switching from
  prefill to decode kernels, costs ~0.014 mean KLD. A fidelity claim below that floor cannot be measured here; one
  above it means something.
- **It applies to any short float matmul at decode**, F16, BF16 and F32 alike. Examples: thin projections, gates,
  hyper-connections, and the routing that upstream #29633 widens.
- **Candidate upstream change:**
  - `mmvf.cu`'s kernel is shared with upstream llama.cpp. The patch is upstream-shaped: no buun-specific code, and
    the default path's SASS is unchanged.
  - It mirrors what #20635 did for MMVQ.

## Not established

- **A HIP build.** The R=2 instantiation is compiled for every target, including warp-64 AMD, where it is never
  launched. The patch has not been built under HIP.
- **Other GPUs.** The rule is enabled for NVIDIA with warp size 32, but only sm_60 was measured. Volta and later
  (different occupancy limits, CUDA graphs on) are untested, and no newer NVIDIA card is available (the 1660 Ti was
  sold 08-18). AMD keeps the old launch.
- **F16 at model level.** F16 accumulates in half2. At k=320 each thread now sums 5 products where it summed 1 (32
  at the k=2048 edge this cap excluded). test-backend-ops' tolerance passed, but no model-level KLD was run on an
  F16-heavy file. B6 covers BF16, which accumulates in float.
- **The amplification mechanism** behind the ~0.014 floor; and whether a smaller-than-floor fidelity difference
  exists between the builds (it would need a much larger corpus or a less sensitive model).
- **hc_down** (few rows, long k) is a different problem, split-k, and was unchanged as expected.
- **k between 1536 and ~3000:** still faster in the grid, excluded by the FP16 cap.
