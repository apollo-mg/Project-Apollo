# Nemotron-3-Diarization on the RX 9070 XT through Vulkan: 17.5 min of meeting audio in 11.5 s (91x real time), same accuracy as CPU

**2026-09-24**, desktop (RX 9070 XT, RADV GFX1201, Mesa 26.2.3, kernel 7.2.6; Ryzen 7 5700X3D). Model card: NVIDIA
Ampere+ only. Runtime: **NeMo-Speech.cpp** `97a15af` (ggml `c03b4e2`), preset **`vulkan-diar`**, `--device vulkan`,
all other settings default. Same model file (`Nemotron-3-Diarization.q8_0.gguf`, sha256 `08456d9e22cd9a32...`),
same audio (AMI ES2004a Mix-Headset, sha256 `3e2560b19bee6952...`) and same reference RTTM
(sha256 `9869c6146c2fd959...`) as `RESULT_NEMOTRON3_DIAR_CPU.md`. All three hashes were re-verified on this box.

**Prior art checked:** `ledger_precheck.py "diarization vulkan"` -> only the CPU receipt from earlier today. This
adds the GPU path, a same-machine CPU baseline, and cross-backend output agreement.

**One meeting, default thresholds; Vulkan 4 runs, each CPU leg 1 run.** This is a speed-and-sanity check, not a benchmark.

## Result

| leg | box | wall | RTF | speed vs real time | CPU | peak RSS |
|---|---|---:|---:|---:|---:|---:|
| **Vulkan**, warm (median of 3) | 9070 XT | **11.5 s** | **0.0110** | **91x** | 66 % | 374 MB |
| Vulkan, first run after build | 9070 XT | 12.2 s | 0.0116 | 86x | 68 % | 373 MB |
| CPU, same binary (`--device cpu`) | 5700X3D | 420 s | 0.400 | 2.5x | 395 % | 462 MB |
| CPU (earlier receipt) | 2x Xeon E5-2650 v3 | 1,155 s | 1.10 | 0.91x | 395 % | 428 MB |

Audio length: 1,049.35 s (17.5 min, 16 kHz mono). **Vulkan is 36x the same box's CPU path and 100x the Xeon.**

## Accuracy is unchanged

| scoring | CPU DER (`.194`) | **Vulkan DER** | CPU confusion | **Vulkan confusion** |
|---|---:|---:|---:|---:|
| collar 0, overlap scored | 21.22 % | **21.38 %** | 1.07 | **1.07** |
| collar 0.25 s | 16.55 % | **16.76 %** | 0.45 | **0.44** |
| collar 0.25 s, overlap excluded | 14.41 % | **14.29 %** | 0.33 | **0.34** |

- 4 of 4 speakers found on both backends.
- **The CPU backend is byte-identical across two different CPUs** (Haswell Xeon on `.194`, Zen 3 on the desktop:
  same 348-segment RTTM, same DER to the hundredth).
- **Vulkan is deterministic:** 3 runs, byte-identical RTTMs.
- **Vulkan and CPU differ slightly** (345 vs 348 segments): the backend's floating-point arithmetic moves a few
  boundaries across the default onset threshold. DER moves by 0.1-0.2 pp in both directions; speaker confusion does
  not move. The difference is systematic, not run-to-run noise.

## Build (desktop: GCC 16.2, CMake 4.4)

Same workarounds as the CPU receipt, nothing installed system-wide:
1. `ninja` via `uv tool install ninja` (the desktop's `ninja` was only a shell alias).
2. `scripts/build_sentencepiece_static.sh` with `CMAKE_POLICY_VERSION_MINIMUM=3.5` and `CXXFLAGS="-include cstdint"`.
3. `scripts/configure.sh vulkan-diar && cmake --build --preset vulkan-diar` (same `CXXFLAGS`). 406 steps, 87 s.

Only the `ggml` submodule is needed. The Vulkan preset uses stock ggml: NVIDIA's pinned patch series applies only
to the CUDA and Metal presets, so nothing in it can block RDNA4.

Timing: `/usr/bin/time` is not installed on this box, so wall time, CPU time and peak RSS come from a Python
`resource.getrusage(RUSAGE_CHILDREN)` wrapper (the same fields `time -v` reports).

## What this adds

- **The GPU path works on AMD, and it is fast.** The card says Ampere+; the model runs on RDNA4 through Vulkan at
  91x real time. An hour of audio is about 40 s.
- **Proof the GPU did the work:** the same binary with `--device cpu` on the same box takes 420 s (2.5x real time)
  and 1,657 s of CPU time; each Vulkan run used about 7.6 s of CPU time in total.
- **No flag needed:** the default `--device auto` picks Vulkan (byte-identical output, same speed).
- **Accuracy survives the backend change** (table above).
- The CPU default is ~4 threads on both machines (393-395 %), and there is no thread flag on `diarize`.

## Not established

- One meeting, default thresholds (the missed-speech share is still the tunable part).
- No CUDA leg (the P100s need NVIDIA's patched ggml; untested on sm_60).
- No comparison against another diarizer on the same audio.
- Raw: `raw/vk_ES2004a.rttm` (Vulkan), `raw/cpu9070box_ES2004a.rttm` (desktop CPU; identical to `raw/nemo_ES2004a.rttm`).
