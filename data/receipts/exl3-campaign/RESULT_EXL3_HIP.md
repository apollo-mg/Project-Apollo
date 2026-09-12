# Result — EXL3 on RDNA4 loads and answers correctly, at CPU speed: no EXL3 weight ever reaches the GPU

**Run 2026-09-12**, on the control plane's RX 9070 XT (gfx1201). The build is buun `9ae8f0f40`
compiled for ROCm (`/mnt/TG_2TB/Projects/buun-9ae8f/build_rocm`), the same commit as `.73`'s
qualification build. The test was preregistered in `PREREG_EXL3_HIP_LOAD.md` (`b2c3a5c`). There is
one instrument fix before any data (`3ac8fe1`), and Amendments 1 (`323f482`) and 2. Raw data is in
`hip/`. This settles ledger entry **O1** of `CAMPAIGN_EXL3.md`.

## Result

The model is turboderp `Qwen3-0.6B-exl3` @ 4.0bpw, with `-ngl 99 -c 4096 -fa on -ctk f16 -ctv f16`:

| id | prediction | result |
|---|---|---|
| P-H1 | it loads and serves a completion; no abort | **CONFIRMED.** Ready in 4.7 s |
| P-H2 | its weights sit on the CPU side, by the summed `model buffer size` lines | **NOT SCORABLE.** The native safetensors loader prints no per-device buffer lines. The prereg allowed for this; the answer came another way (below) |
| P-H3 | it answers the fact question correctly | **CONFIRMED.** "Paris" |
| P-H4, P-H5 | the 27B secondary | **NOT RUN.** Dropped by Amendment 2, before running |

**Decode: 5.91, 6.62 and 6.47 t/s (median 6.47) for a 0.6B model.** At full GPU offload, a GGUF model
of this size would decode in the hundreds of t/s on this card.

## Where the weights live (descriptive, `hip/NOTE_PLACEMENT_AB.md`)

This is the same model and flags, with only `-ngl` varying. Each arm is one 64-token completion:

| `-ngl` | decode | VRAM delta | server RSS |
|---|---|---|---|
| 99 | 4.48 t/s | +0.82 GB | 1.02 GB |
| 0 | 5.24 t/s | +0.25 GB | 1.40 GB |

**Offloading every layer is slightly slower than offloading none.**
- **The weights are in system RAM in both arms.** RSS carries them either way.
- **The extra VRAM at `-ngl 99` is only the KV cache.** A 4096-token f16 KV for this model is about
  0.47 GB, plus the HIP context.

This matches the source. Under `GGML_USE_HIP`, `supports_op` returns false for every EXL3 weight
(`ggml-cuda.cu`: *"HIP supports EXL3 through the CPU expert-cache bridge, not the standalone CUDA
dense/routed executors"*), and the CPU backend runs them (`ggml-cpu/exl3.cpp`). `-ngl` only moves KV
and attention.

## What this means for the campaign

- **O1 is CONFIRMED on hardware and is NOT RETIRABLE BY US.** The control plane can *load* EXL3, which
  is better than an abort, but its GPU does none of the EXL3 work. Serving EXL3 from the always-on box
  would run at CPU speed.
- **Only an upstream HIP executor retires O1.** Mark offered buun RDNA4 testing on 2026-09-12. Two
  facts from source matter for such a port:
  - **The int8 path is the portable one.** Its only intrinsic is an *unsigned* byte dot product
    (`exl3-dq.cuh:17`, `__dp4a(x, 0x01010101u, acc)`). ggml's own `ggml_cuda_dp4a` already maps to
    `__builtin_amdgcn_sudot4` on RDNA3/4 (`common.cuh:726`), and that builtin's sign flags can express
    the unsigned form.
  - **The Ampere GEMV is not portable.** It is inline PTX `mma.sync.aligned.m16n8k16` (`exl3-gemv.cuh:27`),
    so it would need a rewrite or would be skipped. On Pascal, the int8 path is the fast one anyway:
    2.9× faster than reconstruct + cuBLAS (`RESULT_EXL3_SM60_INFERENCE.md`).

## Deviations and limits

- **The first driver refused the primary.** It applied the 27B's 18 GB MemAvailable start guard to the
  0.6B too, and the desktop had 17.8 GB. Preflight exits before the first row, so no data existed. The
  fix (`3ac8fe1`) matches what the prereg says.
- **The primary uses the old EXL3 format** (`0.0.1`, no codebook key). The CPU kernel handled it.
  Whether the `mul1`-codebook 27B also runs on this path was not tested (Amendment 2).
- **`GGML_SCHED_DEBUG=1` printed no split lines in this build,** so per-split backend assignment was
  not captured. The placement evidence is the `-ngl` A/B above, one completion per arm.
- **The decode figures move between runs** (6.47 in the scored primary, 4.48 in the A/B's `-ngl 99`
  arm) on a desktop with other work running. What the A/B supports is the direction: no weight reaches
  VRAM.
