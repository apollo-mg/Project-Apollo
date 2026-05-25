# ROCm 7.2 Gauntlet Stress Test Results (2026-02-28)

### System Baseline: ROCm 7.2.0 (Active) | PyTorch 2.12.0.dev | RX 9070 XT (GFX1201)

### Model Benchmarks (Post-Optimization):
- **DeepSeek-R1 (14B)**: 53.43 t/s (Stable)
- **Qwen3-Coder (30B)**: 31.61 t/s (VRAM Saturated; One-Shot limit verified)
- **Qwen2.5-VL (Vision)**: 91.75 t/s (Optimized Vision Pipeline)

### Tuning Status:
- **AITER MLA**: Active (amd-aiter installed)
- **TunableOp**: tunableop_results0.csv generated (0.16ms GEMM latency)

### Thermal/Power Note:
- Card remained stable throughout saturation test. Cooling confirmed sufficient.