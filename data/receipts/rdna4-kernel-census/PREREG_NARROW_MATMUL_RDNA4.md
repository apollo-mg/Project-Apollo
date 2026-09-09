# Pre-registration — RDNA4 (gfx1201) narrow-matmul census

**Registered:** 2026-09-09, before any result was observed.
**Context:** jasstrong's narrow-matmul work on `TheTom/llama-cpp-turboquant` #362 / #363.
He posted a perf table for gfx90a / gfx1100 / gfx1030 and reported an unfiled crash.
**gfx1201 (RX 9070 XT, RDNA4) is absent from both.** This machine is the only RDNA4 in that thread.

## Shapes under test

Derived from the hypercloning tensors in his example model:

| name | weight | m | k |
|---|---|---|---|
| `hc_*_inject`  | `[10240, 4]`   | 4     | 10240 |
| `hc_head_down` | `[10240, 320]` | 320   | 10240 |
| `hc_head_up`   | `[320, 10240]` | 10240 | 320   |

## What the source says before we measure

From `ggml/src/ggml-cuda/mmvf.cu` + `common.cuh` in the local buun clone at `a56eeef5`,
`should_use_mmvf()` thresholds on AMD:

| dtype | CDNA | RDNA3 | RDNA4 |
|---|---|---|---|
| F32  | `ne11 <= 3` | `ne11 <= 8` | `ne11 <= 8` |
| F16  | `ne11 <= 2` | `ne11 <= 3` | **`ne11 <= 5`** (explicitly tuned) |
| BF16 | `ne11 <= 3` | `ne11 <= 3` | **`ne11 <= 3`** (no RDNA4 case — flat default) |

The F32 path in #363 is gated behind `fp32_mma_hardware_available()`, which is
`GGML_CUDA_CC_IS_CDNA(cc)` only. **So #363's headline F32 case cannot affect RDNA4.**
The open question the source raises instead is BF16: F16 got an RDNA4-specific
threshold and BF16 did not.

## Predictions (logged before the run)

**P1 — the crash.** `MUL_MAT type_a=q8_0, m=10240, n=4, k=320` does **NOT** segfault on gfx1201.
Confidence **80%**. Reasoning: reported faulting on gfx1030 (RDNA2) but clean on both gfx1100
(RDNA3) and gfx90a (CDNA). RDNA4 is downstream of the clean RDNA3 path, so a RDNA2-specific
codegen/occupancy bug is the likeliest shape of it. *Falsified if exit code is 139.*

**P2 — the BF16 cliff.** On `m=10240, k=320`, BF16 shows a throughput discontinuity between
n=3 and n=4 that F16 does not show until between n=5 and n=6, because BF16 drops out of mmvf
at `ne11 > 3` while F16 stays in through `ne11 <= 5`.
Confidence **70%**. *Falsified if BF16 n=3→4 is smooth, or if F16 breaks at the same n as BF16.*

**P3 — magnitude.** If P2 holds, the BF16 penalty at n=4 vs n=3 is **> 1.3×**.
Confidence **50%**. Deliberately the weakest claim — I have no prior on the fallback path's cost
at this shape, only on whether the branch changes.

**P4 — the narrow-output shape.** `m=4, k=10240` is the worst of the three shapes by achieved
bandwidth fraction, because it reads a full 10240-deep reduction to produce 4 outputs.
Confidence **75%**.

## Guards

- Job blocks until the GPU is quiet for 3 consecutive 30s checks (no `llama-server`,
  no `run_agent.py`/`run_real.py`, GPU use ≤15%). A single check can land in the gap while
  the harness restarts between phases; AFM-36 says orphaned workers outlive their bench.
- Filters were validated on the **CPU backend** before queueing: they select 1 / 12 / 14 cases.
  This was a live catch — the first version filtered `test` mode against shapes that exist only
  in `make_test_cases_perf()`, so it would have matched **zero** cases and exited 0,
  reporting "no segfault" without executing anything. See `readiness-probes-lie`.
- Script warns and refuses to be trusted if it emits fewer perf lines than cases selected.
- Clock state recorded at start (`gpu-clock-benchmark-discipline`).

## Scope

Local test cases are marked `LOCAL (2026-09-09, not upstream)` in `tests/test-backend-ops.cpp`
in both `make_test_cases_eval()` and `make_test_cases_perf()`. Nothing goes to Tom or jasstrong
without Mark's explicit approval and his own words.
