# Result — buun `aad850104` fixes the VBR decode regression on the 9070, and overshoots it

**Run 2026-09-11 19:06–19:15, RX 9070 XT at 330 W.** Pre-registered in `PREREG_SPEED_AAD85.md`
(commit `aa1febe`, 19:06:11, before the first run). Raw `llama-bench` output is in
`fix-ab/bench_aad85/`; the driver is `fix-ab/speed_ab_aad85.sh`.

**Setup:**
- **Model:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp`.
- **Common flags:** `-ngl 99 -fa 1`.
- **Order:** two rounds, OLD, FIX, NEW then NEW, FIX, OLD.

## Result

Each cell is the mean of the two rounds, in t/s; the round values are in brackets.

| config | OLD `3823c9eb6` | FIX `a334fc01e` | NEW `aad850104` | NEW vs FIX | NEW vs OLD |
|---|---|---|---|---|---|
| pp512, f16, empty | 965.4 (969.5 / 961.3) | 980.4 (980.6 / 980.1) | 979.3 (980.5 / 978.0) | −0.1% | +1.4% |
| tg128, f16, empty | 30.34 (30.50 / 30.18) | 31.13 (31.21 / 31.05) | 31.27 (31.27 / 31.26) | +0.4% | +3.0% |
| tg128 @ 13k, f16 | 28.92 (28.93 / 28.91) | 29.71 (29.55 / 29.87) | 29.86 (29.88 / 29.84) | +0.5% | +3.3% |
| **tg128 @ 13k, VBR** | 27.57 (27.56 / 27.58) | 25.26 (25.23 / 25.29) | **28.88 (28.87 / 28.88)** | **+14.3%** | **+4.7%** |

## Predictions

| id | prediction | conf | result |
|---|---|---|---|
| P-S1 | VBR: NEW within 2% of OLD | 65% | **FALSIFIED**, in the good direction: NEW is 4.7% *faster* than OLD |
| P-S2 | VBR: NEW at least 4% faster than FIX | 75% | **CONFIRMED** — +14.3% |
| P-S3 | f16 decode (empty context and 13k): NEW within ±2% of FIX | 60% | **CONFIRMED** — +0.4% and +0.5% |

## What it means

- **The regression is gone, and VBR is now cheaper than before it appeared.** At 13k depth, VBR
  decode costs this much against f16:

  | build | VBR vs f16 |
  |---|---|
  | NEW | 3.3% |
  | OLD | 4.7% |
  | FIX | 15.0% |

- **The new HIP runtime wrappers show no cost here.** Those are the staged pageable copies and the
  per-launch attribute lookup from `e2de1fff6`. f16 decode and pp512 are within ±0.5% of FIX. Model
  load time was not measured.
- **The mechanism matches the source reading but is not attributed.** The source change is that HIP
  builds regain the `GGML_CUDA_TURBO_FA` define. But there are three commits in the range, and no
  per-commit builds were made.
  - llama-bench does not print backend features, so `TURBO_FA = 1` was not observed directly.
- **NEW's VBR runs are noisier within a run:** ±0.76–0.79, against ±0.10–0.28 for the other builds.
  The two rounds still agree to 0.01 t/s.
- **Drift between sessions is controlled by the rotation, not removed.** At 13:31, OLD's VBR measured
  26.94 / 27.05 t/s; here it measured 27.56 / 27.58. Only comparisons within this session are made.

## Also found: master `aad850104` does not compile for Pascal (sm_60)

Building the same commit for `.73` (CUDA 12.4, `CMAKE_CUDA_ARCHITECTURES=60`) fails in two groups of
new code. All of it arrived after `.73`'s last good build (`a56eeef5`, 09-07).

**1. One-shot all-reduce: `allreduce-oneshot.cu`, from `e5d5ea9d5` (09-08).**
- **The constructs.** It uses three sm_70-only constructs: `__nanosleep` (line 70) and inline PTX
  `ld.acquire.sys` and `st.release.sys` (lines 53 and 57).
- **Guards are safe here.** The runtime already refuses this path below Volta:
  `ggml_cuda_ar_oneshot_init`, line 425, returns nullptr.
- **Upstream already has the pattern.** `allreduce.cu` uses `#if __CUDA_ARCH__ >= GGML_CUDA_CC_VOLTA`
  with `NO_DEVICE_CODE` in the else branch, and plain volatile flag loads and stores plus
  `__threadfence_system()`.
- **Verified: guarding all three makes the file compile for sm_60.** Guarding `__nanosleep` alone was
  not enough; ptxas then rejected `.acquire` and `.release`.
  - The patch is in `.73`'s scratch worktree only (`~/buun-aad85/LOCAL_PATCH_sm60_guards.diff`).
  - It uses volatile fallbacks and omits `NO_DEVICE_CODE`. That is dead code either way; upstream
    should follow `allreduce.cu`.

**2. EXL3 and int8-channel kernels.** These are `exl3*.cuh` and `exl3.cu` (from `418619d76` and
`182fe0286`, 09-06), and `int8-channel.cu` (from `2ff45c668`). None of the EXL3 files has any
architecture guard.
- **Unsigned `__dp4a` in EXL3.** `exl3-dq.cuh:54,55,103` and `exl3-gemv.cuh:36,37` call the
  **unsigned** `__dp4a` overload, which needs sm_61+.
  - This is the compiler error that stopped the build.
  - `ggml_cuda_dp4a()` is the *signed* variant. Swapping it in would compile but change the result
    for any byte ≥ 128, so this needs a guarded unsigned fallback.
- **Signed `__dp4a` in `int8-channel.cu`.** Lines 417–474 call `__dp4a` on `int4` operands, which are
  signed. `ggml_cuda_dp4a()` fits there.
- **Ampere-only instructions in EXL3, by PTX ISA requirements.** `exl3-gemv.cuh:26` uses
  `mma.sync.aligned.m16n8k16…f16`, and `exl3-gemv-int8.cuh:34–38` uses `cp.async`. Both require sm_80+
  per the PTX ISA.
  - If that holds, this code also breaks sm_70 and sm_75 builds. **Not compile-tested here.**
- **Status:** a keep-going build of the CUDA backend on `.73` is enumerating the complete list of
  sm_60 errors.

`.73`'s daily-driver binary is untouched. Nothing has been pushed upstream.

## Not retested

- **Runaways.** `a334fc01e`'s 0/33 stands for that commit only.
- Other models, other cards, and prefill at depth.
