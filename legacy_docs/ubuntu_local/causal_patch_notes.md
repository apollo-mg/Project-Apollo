# Causal-Conv1d AMD ROCm (RDNA 4) Build Patch Notes
**Date:** March 2026
**Environment:** ROCm 7.2.0, PyTorch 2.12.0 (Nightly), RX 9070 XT (gfx1201)

## The Issue
The official `dao-ailab/causal-conv1d` installer (v1.6.0) is fundamentally broken for native AMD builds because its `setup.py` contains hardcoded assumptions about the presence of NVIDIA CUDA tools (`nvcc`), even when `torch.version.hip` is active.

### Specific Failures
1.  **`get_cuda_bare_metal_version(cuda_dir)`**: This function attempts to run `subprocess.check_output([cuda_dir + "/bin/nvcc", "-V"])`. On an AMD system, `/opt/rocm/bin/nvcc` does not exist, causing a fatal `FileNotFoundError`.
2.  **`bare_metal_version` undefined**: If the `try/except` block catches the file error, it fails to define the variable `bare_metal_version`, resulting in a `NameError` later in the script when it tries to compare versions.
3.  **Compiler Flag Errors (The "nvcc fake" trap)**: If you attempt to trick the installer by symlinking `hipcc` to `nvcc`, the installer successfully detects the compiler but then passes NVIDIA-specific architecture flags (e.g., `-gencode arch=compute_62...`) to the AMD compiler (`amdclang++`), resulting in fatal `clang++: error: unknown argument` failures during ninja compilation.

## The Reality for RDNA 4 Users
You **cannot** currently compile `causal-conv1d` from source on a purely native AMD machine using the standard `pip install` or `setup.py` without extensive modifications to the PyTorch C++ extension builder logic to prevent it from injecting CUDA-specific flags into the HIP compiler.

### Conclusion
The "slow path" fallback (which causes high CPU usage and ~320W GPU power draw during inference) is currently the only stable way to run the Qwen 3.5 unified vision architecture on RDNA 4 until the `causal-conv1d` maintainers refactor their build scripts to correctly identify and pass `hipcc` flags when ROCm is detected.
