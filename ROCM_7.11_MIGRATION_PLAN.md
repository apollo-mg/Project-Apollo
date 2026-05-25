# ROCm 7.11 Transition Planning & Analysis

*Document created: March 29, 2026*
*Target Architecture: AMD RDNA4 (RX 9070 XT) running CachyOS (Arch Linux)*

## Overview
ROCm 7.11.0 is the leading edge of AMD's new "TheRock" modular build system, intended to eventually replace the monolithic 7.2.x production stream by mid-2026. While it brings native package manager support (`.deb`/`.rpm`) and official RDNA 4 support, it is currently a "Technology Preview" with significant known regressions affecting local LLM inference.

## Key Changes Relevant to Sovereign Lab

### 1. Hardware & Driver Integration
*   **Official RDNA 4 Support:** The release notes explicitly confirm support for the `gfx1201`/`gfx1200` targets, which includes the **Radeon RX 9070 XT**.
*   **Compute vs. Graphics:** This preview focuses heavily on compute. Mixed workloads (running a 60fps GUI alongside heavy inference) require specific Radeon Software for Linux driver stacks, which may complicate the CachyOS rolling release model.

### 2. The Local AI Stack Regressions (CRITICAL)
Currently, ROCm 7.11.0 introduces several known issues that directly threaten the `llama-server` and `buddy_agent.py` pipelines:
*   **llama.cpp Prompt Processing:** There is a known performance regression causing slower prompt evaluation across all architectures.
    *   *Workaround:* Requires compiling with `-mllvm --amdgpu-unroll-threshold-local=600`.
*   **Clang Compilation Bug:** Using `-O0` optimization during compilation on Radeon GPUs triggers "illegal instruction" errors (which will crash `llama.cpp` builds).
    *   *Workaround:* Must compile with `-Og` instead.
*   **Model Validation Failures:** AMD reported that Llama 3.1 (8B/70B) and Llama 2 (70B) failed validation in this preview. Since the Architect brain relies on heavily quantized 35B/30B models, these underlying architecture failures are highly concerning.

### 3. Packaging & OS Ecosystem
*   **The Shift to Native:** AMD is finally moving to native `.deb` and `.rpm` packages, ditching their old custom installer scripts.
*   **The Arch/CachyOS Gap:** The preview does *not* support Arch natively. We will be entirely reliant on the CachyOS maintainers to adapt the new "TheRock" build system into `pacman` packages.

---

## Migration Checklist & Open Questions

Before attempting to upgrade the Sovereign Lab to the 7.11/TheRock architecture (likely in mid-2026 when it hits production), we must answer the following:

1.  **CachyOS Adaptation:** Have the CachyOS maintainers successfully ported the "TheRock" modular SDKs to the Arch Build System (AUR/CachyOS Extra)? 
2.  **llama.cpp Resolution:** Has the prompt processing performance regression in `llama.cpp` been resolved upstream, or do we need to bake the `-mllvm` compiler flags into our `bootstrap_apollo.sh` script?
3.  **Model Stability:** Are Qwen and Llama-based architectures passing validation again? (A failing Llama 3.1 validation implies underlying PyTorch/HIP memory mapping issues).
4.  **Mixed Workload Stability:** Will the new driver stack allow the RX 9070 XT to smoothly handle the PyQt6 `dynamic_canvas.py` 60fps render loop while simultaneously crunching 35B parameter matrices in the background?

## Recommendation
**Do not deploy ROCm 7.11.0 Preview to the primary hardware.** Wait for the regressions in `llama.cpp` and Llama 3.x validation to be cleared, and for CachyOS to officially package it via `pacman`. Maintain current operations on ROCm 7.2.0-2.
