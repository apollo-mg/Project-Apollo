# Pre-registration — does buun `aad850104` restore VBR decode speed on the 9070?

**Logged 2026-09-11, before any benchmark run of `aad850104`.**

## The question

`RESULT_FIX_A334FC01E.md`'s speed follow-up measured a **−7% VBR decode regression** on the 9070:
VBR at 13k depth went from 27.0 t/s to 25.0 t/s between OLD `3823c9eb6` and FIX `a334fc01e`. The f16
paths gained 3%. buun says master `aad850104` ("hip: restore Turbo flash-attention dispatch") fixes
it.

**What the source says.** HIP builds never defined `GGML_CUDA_TURBO_FA`, so Turbo's shared
flash-attention dispatch was off. `aad850104` adds the define in `ggml/src/ggml-hip/CMakeLists.txt`.
The range `a334fc01e..aad850104` has two other changes that could move speed either way:
- **`e2de1fff6`:**
  - pageable host↔device copies over 1 MiB now go through a 1 MiB pinned staging buffer, with a sync
    per chunk;
  - every HIP kernel launch first calls `hipFuncGetAttributes`.
- **`c74a53314`:** VBR's HIP VMM commit granularity goes from 64 KiB to 256 KiB.

## Builds

All three are ROCm builds with the same CMake flags: `GGML_HIP=ON`, `AMDGPU_TARGETS=gfx1201`,
`GGML_HIP_NO_VMM=OFF`, Release, `GGML_NATIVE=ON`.

| label | commit | binary |
|---|---|---|
| OLD | `3823c9eb6` | `engines/buun-llama-cpp/build_rocm` |
| FIX | `a334fc01e` | `/mnt/TG_2TB/Projects/buun-master/build_rocm` |
| NEW | `aad850104` | `/mnt/TG_2TB/Projects/buun-aad85/build_rocm`, built 2026-09-11 19:02 |

## Protocol, identical to the follow-up

- **Model:** `gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf`.
- **Common flags:** `llama-bench -ngl 99 -fa 1`.
- **Configs:**
  - **E:** `-ctk f16 -ctv f16 -p 512 -n 128 -r 3`, i.e. pp512 and tg128 on an empty context.
  - **F:** `-ctk f16 -ctv f16 -p 0 -n 128 -d 13000 -r 2`.
  - **V:** `-ctk vbr -ctv vbr -p 0 -n 128 -d 13000 -r 2`.
- **Rounds:** two, in the order OLD, FIX, NEW, then NEW, FIX, OLD.
- **Conditions:** RX 9070 XT at 330 W, no other GPU work.
- **Driver:** `fix-ab/speed_ab_aad85.sh`, output in `fix-ab/bench_aad85/`.
- **Statistic:** per build and config, the mean t/s of the two rounds.

## Predictions

| id | prediction | conf |
|---|---|---|
| P-S1 | V: NEW is within 2% of OLD. The regression is gone | 65% |
| P-S2 | V: NEW is at least 4% faster than FIX | 75% |
| P-S3 | E tg128 and F: NEW is within ±2% of FIX, i.e. the new HIP runtime wrappers cost nothing on the f16 path | 60% |

## What will not be claimed

- Nothing about other models, other cards or prefill beyond pp512.
- **Not a retest of the runaway fix.** `a334fc01e`'s 0/33 result stands for that commit;
  `aad850104` is not retested for runaways here.
- **No attribution between changes.** With three commits in the range, a speed change cannot be
  pinned to one of them without per-commit builds.
