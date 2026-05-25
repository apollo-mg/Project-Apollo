# Forge Entry: Sovereign Engine GFX1201 (March 2026)
**Subject:** Bare-metal PyTorch 2.4.0 Compilation on RDNA 4
**Author:** Apollo Architect (Gemini Pro) + Mark

## 🛠️ Breakthroughs
1. **The C/C++ Linkage Bridge**: Renaming `.c` files to `.cpp` in Torch Dynamo and Functorch to bypass `amdclang` standard injection, while preserving C-linkage via `extern "C"`.
2. **The ABI Bridge**: Creation of `libtorch_abi_fix.so` to resolve template mismatch symbols between CPU and HIP compilation units (e.g., `const_data_ptr`).
3. **The Hybrid Sovereign Core**: A dual-backend architecture using `vLLM` (Port 8000) for resident Gatekeeper triage and `Ollama` (Port 11434) for dynamic specialist models with automated SysRAM spillage.

## ⚡ Performance Baseline (Pre-Optimized)
- **Qwen 3.5 4B Aggressive**: 78.07 TPS (Eval) / 1,457.62 TPS (Prefill).
- **Qwen 3.5 0.8B**: 140.70 TPS (Eval) / 1,696.63 TPS (Prefill).

## 🚀 Optimization Strategy
- **Guided Decoding**: Standardized all tool calls to use Full JSON Schema in the `format` parameter for 100% deterministic execution.
- **VRAM Tetris**: Locked Gatekeeper to vLLM to ensure zero-latency triage during heavy background builds.
