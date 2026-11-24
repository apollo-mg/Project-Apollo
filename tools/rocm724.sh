#!/usr/bin/env bash
# Run a desktop ROCm binary built before 2026-11-24 on the ROCm 7.2.4 libraries it was built against.
# Why: the 2026-11-24 CachyOS update moved the system ROCm 7.2.4 -> 10.1; every llama.cpp build_rocm made against 7.2.4
# segfaults (exit 139) while uploading weights under 10.1. The 7.2.4 packages, unpacked from the pacman cache into a
# private tree (no system change), restore them: FZ_BASE and Q35R replayed 240 of 240 byte-identical
# (data/receipts/stack-drift/). PyTorch in venv_cachyos bundles its own ROCm and needs none of this.
# Usage: tools/rocm724.sh <command> [args...]      e.g. tools/rocm724.sh engines/.../build_rocm/bin/llama-server -m ...
P=${ROCM724:-/mnt/TG_2TB/AI/rocm-7.2.4/opt/rocm}
[ -f "$P/lib/libamdhip64.so.7" ] || { echo "rocm724: no ROCm 7.2.4 tree at $P" >&2; exit 1; }
export LD_LIBRARY_PATH="$P/lib:$P/lib/llvm/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ROCBLAS_TENSILE_LIBPATH="$P/lib/rocblas/library"
exec "$@"
