#!/usr/bin/env bash
# Cross-build test-backend-ops for the GTX 1660 Ti (TU116, sm_75) on .194, to run on .76.
#
# WHY CROSS-BUILD: .76 is the bench rig holding the 1660 Ti, but it is an amnesiac live USB --
# 7 GB RAM, 10 GB RAM-backed overlay, no nvcc. Installing CUDA there would thrash the box and
# evaporate on reboot. .194 has CUDA 12.4 and 40 cores.
#
# TWO PORTABILITY CONSTRAINTS, both learned the hard way on this fleet:
#   1. .76's CPU is a Pentium G3258 -- Haswell with AVX/AVX2/FMA/F16C/BMI2 fused OFF, SSE4.2
#      only. Building on .194's Xeon E5-2650 v3 with -march=native would emit AVX2 and SIGILL.
#      Hence GGML_NATIVE=OFF and every ISA feature explicitly off.
#   2. The .note.gnu.property ISA stamp. On CachyOS, crt1.o stamps x86-64-v3 on every binary
#      regardless of -march, which makes it refuse to start on pre-AVX CPUs. Ubuntu 26.04's
#      crt1.o stamps x86-64-baseline (verified), so this direction is safe -- but the built
#      binary is checked below rather than assumed.
#
# WHAT IT IS FOR: Tom flagged the GQA mis-tiling question as Turing-specific and untestable
# ("whenever Turing hardware shows up"). Comparison form is already confirmed correct on
# gfx1201 (mine) and sm_120 (his). sm_75 would be the third vendor/arch.
set -u
REPO=/home/mark/llama_tq_ds4
WT=/home/mark/tq_sm75
B=$WT/build_sm75
TARGET=75a24b8f2
log(){ echo "[$(date '+%F %T')] $*"; }

log "=== fetching TheTom/llama-cpp-turboquant ==="
cd "$REPO" || exit 1
git remote get-url thetom >/dev/null 2>&1 || git remote add thetom https://github.com/TheTom/llama-cpp-turboquant.git
git fetch -q thetom 2>&1 | tail -3
git rev-parse --verify -q "${TARGET}^{commit}" >/dev/null || { log "FATAL: $TARGET not found after fetch"; exit 1; }
log "  target: $(git log --oneline -1 $TARGET)"

if [ ! -d "$WT" ]; then
	git worktree add --detach "$WT" "$TARGET" 2>&1 | tail -2
else
	git -C "$WT" checkout -q --detach "$TARGET"
fi
log "  worktree HEAD: $(git -C "$WT" log --oneline -1)"
log "  gqa form (non-volta, line 92): $(sed -n '92p' "$WT/ggml/src/ggml-cuda/fattn.cu" | tr -s ' ')"

log "=== configure (CUDA arch 75, all x86 ISA extensions OFF) ==="
cmake -S "$WT" -B "$B" \
	-DCMAKE_BUILD_TYPE=Release \
	-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75 \
	-DGGML_NATIVE=OFF -DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_AVX512=OFF \
	-DGGML_FMA=OFF -DGGML_F16C=OFF -DGGML_BMI2=OFF \
	-DLLAMA_CURL=OFF -DLLAMA_BUILD_SERVER=OFF \
	> /home/mark/sm75_cfg.log 2>&1 || { log "CONFIGURE FAILED"; tail -15 /home/mark/sm75_cfg.log; exit 1; }
log "  configured."

log "=== build test-backend-ops ==="
make -C "$B" test-backend-ops -j"$(nproc)" > /home/mark/sm75_build.log 2>&1 || {
	log "BUILD FAILED:"; grep -E "error:" /home/mark/sm75_build.log | head -8; exit 1; }
log "  built: $(ls -la $B/bin/test-backend-ops | awk '{print $5" bytes"}')"

log "=== portability checks ==="
log "  ISA stamp: $(readelf -n "$B/bin/test-backend-ops" 2>/dev/null | grep -i 'x86 ISA needed' | tr -s ' ' || echo 'none (good)')"
log "  AVX/AVX2 instructions present in .text?"
if objdump -d "$B/bin/test-backend-ops" 2>/dev/null | grep -qE "\s(vpxor|vmovdqa|vfmadd|vbroadcast)"; then
	log "    *** AVX-family instructions FOUND in the test binary -- would SIGILL on G3258 ***"
else
	log "    none found (good)"
fi
log "  cudart linkage: $(ldd "$B/bin/test-backend-ops" 2>/dev/null | grep -iE 'cudart|cublas' | tr -s ' ' | head -3 || echo 'static (good)')"
log "=== DONE ==="
