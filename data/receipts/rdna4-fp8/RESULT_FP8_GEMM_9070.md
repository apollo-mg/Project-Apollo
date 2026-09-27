# PyTorch on ROCm 7.2 uses the RX 9070 XT's FP8 matrix units: FP8 GEMM runs 2.8x bf16 and INT8 matches it, while the CUDA-to-AMD route through SCALE cannot reach FP8 at all

**2026-09-27.** RX 9070 XT (gfx1201, 16 GB, desktop session resident, ~1.7 GB in use). `venv_cachyos`:
torch `2.13.0+rocm7.2`, HIP `7.2.53211`. Probe `fp8_probe.py` (this directory); raw output of three runs in
`fp8_probe_runs.txt` (the first run is in the session only; runs 2-3 are the file).

**Prior art:** `ledger_precheck.py "FP8 GEMM RDNA4 gfx1201 scaled_mm int8 throughput"` found no receipt on this. The
related one is `atlas-gfx1201/RESULT_S1_CENSUS_PROBES.md`: through SCALE (CUDA source compiled for gfx1201), an e4m3
`mma.sync` fails with "does not know how to codegen the PTX type: e4m3", and the hardware e4m3 `cvt` is rejected too.
**What this adds:** the same card through the native ROCm stack, where FP8 is reachable, and how fast it is.

## Result (8192 x 8192 x 8192 GEMM, 20 timed reps after one warm-up, three runs)

| path | throughput | vs bf16 |
|---|---:|---:|
| bf16 `matmul` | 70.4-70.7 TFLOPS | 1.00x |
| FP8 e4m3fn (OCP) `torch._scaled_mm`, bf16 out | **196.2-197.5 TFLOPS** | **2.8x** |
| INT8 `torch._int_mm` | 192.1-192.3 TOPS | 2.7x |
| FP8 e4m3fnuz (MI300-style) `_scaled_mm` | `HIPBLAS_STATUS_NOT_SUPPORTED` | -- |

- **Numerics:** FP8 GEMM output against bf16 GEMM of the same FP8-quantized inputs: max relative error 3.8-3.9e-3.
  The FP8 path is doing real FP8 math and agrees with the upcast reference to within accumulation differences.
- **Format:** RDNA4 takes the OCP `e4m3fn` format (as NVIDIA does), not the `fnuz` variant that MI300 uses. Code or
  checkpoints that assume AMD means fnuz will fail here.
- **INT8 and FP8 run at the same rate.** So between an INT8 and an FP8 checkpoint of the same model, quality decides,
  not speed. For Qwen-Image-2.1, Unsloth reports INT8 closer to bf16 (LPIPS 0.064 against FP8's 0.112).

## What it means

- **For Metrale on RDNA4:** FP8 speed on gfx1201 is real, but SCALE can't reach it today. A native HIP path (hipBLASLt,
  or gfx12 WMMA intrinsics) can. That is the case for giving the gfx1201 target a HIP FP8 path next to SCALE, like the
  `strix-hip` tree.
- **For local image and LLM stacks on the 9070 (PyTorch, diffusers, Unsloth):** FP8 and INT8 weights are not just a
  memory saving; the matrix math runs about 2.7-2.8x bf16 at large shapes.

## Not established

- **One large square shape, synthetic inputs, unit scales.** Real layers are smaller and batch-1 decode is
  memory-bound, so end-to-end model speedups will be far smaller than 2.8x. The GEMM rate is an upper bound.
- **Clocks were not pinned or recorded during the runs.** A desktop session shared the card, and the three runs agree
  within about 1%.
- **Power was not measured.**
