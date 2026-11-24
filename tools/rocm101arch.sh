#!/usr/bin/env bash
# Run a ROCm 10.1 build on the desktop with Arch's hip-runtime-amd 10.1-2 (libamdhip64) in place of CachyOS's 10.1-2.1.
# Why: CachyOS's x86_64_v3 build of the 10.1 HIP runtime segfaults creating a second HIP stream (17 of 20 runs of a
# 10-line test; every llama.cpp crash lands on the same instruction). Arch's build of the same version: 0 of 20.
# Everything else stays the system's ROCm 10.1. data/receipts/stack-drift/NOTE_CACHYOS_HIP_BUG.md
# Usage: tools/rocm101arch.sh <command> [args...]
P=${ROCM101ARCH:-/mnt/TG_2TB/AI/rocm-10.1-arch/hip/opt/rocm/lib}
[ -f "$P/libamdhip64.so.7" ] || { echo "rocm101arch: no Arch HIP runtime at $P" >&2; exit 1; }
export LD_LIBRARY_PATH="$P${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$@"
