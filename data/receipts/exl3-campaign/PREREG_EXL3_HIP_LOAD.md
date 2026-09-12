# Prereg — EXL3 on RDNA4: refused, or routed to the CPU? (EXL3 campaign, test 2, ledger O1)

**Written 2026-09-12 ~15:25, before any HIP EXL3 run.**

## What the source says (buun `9ae8f0f40`)

- **The GPU declines EXL3.** In `ggml-cuda.cu`, `supports_op` returns **false** for every EXL3 weight
  under `GGML_USE_HIP`, for `MUL_MAT` and `MUL_MAT_ID` alike. The code comment reads: *"HIP supports
  EXL3 through the CPU expert-cache bridge, not the standalone CUDA dense/routed executors."*
- **The CPU backend implements EXL3.** See `ggml-cpu/exl3.cpp` (`ggml_cpu_exl3_compute`) and the type
  traits with `dequantize_row_exl3`.
- **So the expectation is that it loads, and the GPU does none of the EXL3 matmuls.** This test checks
  that on hardware. The older local ROCm binaries contain no EXL3 code at all, so they cannot answer it.

## Setup

- **Hardware:** the control plane's RX 9070 XT (gfx1201).
- **Build:** buun `9ae8f0f40` built for ROCm at `/mnt/TG_2TB/Projects/buun-9ae8f/build_rocm` (server
  target only). It is the same commit as `.73`'s qualification build.
- **Server:** port 8195, with `-ngl 99 -c 4096 -np 1 -fa on -ctk f16 -ctv f16 --jinja`.
- **Primary model:** turboderp `Qwen3-0.6B-exl3` @ 4.0bpw, the local snapshot used in the sm_60 receipt
  (format `0.0.1`, no codebook key).
- **Stages:**
  - **load:** readiness means a real completion. The row records each `<device> model buffer size` line
    from the server log.
  - **fact:** a one-word capital question, with thinking off and temperature 0.
  - **speed:** 3 × 128 greedy tokens.

## Predictions

| id | prediction |
|---|---|
| P-H1 | The 0.6B loads and serves a completion. It does not abort |
| P-H2 | Its weights sit on the CPU side: the summed `model buffer size` for CPU devices exceeds the ROCm0 figure |
| P-H3 | It answers the fact question correctly (the answer contains "Paris"), so the CPU EXL3 compute is correct |

**Secondary.** It runs only after `.73`'s test-1 window has ended, and only if P-H1 holds. The model is
turboderp `Qwen3.8-27B-exl3` @ 4.00bpw (`mul1` codebook), with the same flags.

| id | prediction |
|---|---|
| P-H4 | The 27B loads |
| P-H5 | It decodes **below 3 t/s**. That would be CPU-bound: about 14 GB of weights read per token over the 5700X3D's dual-channel DDR4. For comparison, a 12 GB IQ3_XXS GGUF of the same model decodes at 32.1 t/s on this GPU (measured 2026-08-21) |

## Declared in advance

- **A format failure is not a HIP verdict.** If the 0.6B fails to load with an error that names its
  format (`0.0.1`, no codebook), that is not an O1 verdict. The secondary then decides P-H1's question on
  the 27B instead.
- **P-H2 is scored from log lines of the form `<device> model buffer size = N MiB`.** If the native
  loader prints none, P-H2 is **NOT SCORABLE**.
- **The 27B is a secondary because it puts about 14 GB of weights in system RAM.** The desktop has 31 GB,
  about 19 GB of it available. The driver refuses to start below 18 GB MemAvailable and kills the server
  if MemAvailable falls under 3 GB. Such a kill is recorded as a memory abort, not a load failure.
- **A pass does not retire O1.** EXL3 at CPU speed is not a way to serve from the control plane; only a
  HIP executor would change that. Mark has offered buun RDNA4 testing.

**Driver and scorer:** `exl3_hip_load.py` (`primary`, `secondary` or `score`). Results go to `hip/`.
