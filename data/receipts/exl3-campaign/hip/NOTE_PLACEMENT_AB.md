# Note — where EXL3 weights live on RDNA4 (descriptive, not preregistered)

**2026-09-12 ~15:34**, control plane RX 9070 XT (gfx1201), buun `9ae8f0f40` built for ROCm
(`/mnt/TG_2TB/Projects/buun-9ae8f/build_rocm`). Model: turboderp `Qwen3-0.6B-exl3` @ 4.0bpw, a 636 MB
snapshot. Flags fixed at `-c 4096 -np 1 -fa on -ctk f16 -ctv f16`; only `-ngl` varies. One 64-token
greedy completion each.

| `-ngl` | decode | VRAM delta | server RSS |
|---|---|---|---|
| 99 | 4.48 t/s | +0.82 GB | 1.02 GB |
| 0 | 5.24 t/s | +0.25 GB | 1.40 GB |

**Offloading every layer is slightly slower than offloading none.** The weights are in system RAM in
both cases — RSS carries the ~0.64 GB of weights either way, and at `-ngl 0` it also carries the KV
cache. The extra VRAM at `-ngl 99` matches what a 4096-token f16 KV needs for this model (28 layers ×
2 × 8 KV heads × 128 × 4096 × 2 B ≈ 0.47 GB) plus the HIP context, with no room for weights.

**This is what `supports_op` says in source:** under `GGML_USE_HIP`, EXL3 returns false for `MUL_MAT`
and `MUL_MAT_ID`, so the weights are placed in CPU buffers and every EXL3 matmul runs on the CPU
backend (`ggml-cpu/exl3.cpp`). `-ngl` only moves KV and attention.

**Why this is descriptive:** it is one completion per arm, on a desktop with other work running, and it
was run after the preregistered primary. The decode figures move a little between runs (the
preregistered primary's median was 6.47 t/s over 3 × 128 tokens). The *direction* — no weight ever
reaching VRAM — is what this note supports.

**Not evidence about:** `GGML_SCHED_DEBUG=1` printed no split lines in this build, so per-split backend
assignment was not captured. Raw logs: `place_ngl99.log`, `place_ngl0.log`.
