#!/usr/bin/env bash
# Build upstream llama.cpp at any ref for an Abstend host, in its own checkout, configured as our earlier builds:
#   sm60    (.194, 4x P100): CUDA, arch 60, gcc-13 host compiler (CUDA 12.4), FA on, sched copies 4 -> build_sm60
#           as ripple/build_67107ac_sm60.sh and ds41-h2h/build_b12063_sm60.sh
#   gfx1201 (desktop 9070 XT): HIP via hipconfig, arch gfx1201, FA on, sched copies 4 -> build_rocm
#           as engines/llama_cpp_upstream_f74e2fa/build_rocm
# REF is a commit, a tag, or a GitHub pull request ("pr/31692" fetches refs/pull/31692/head): release-day support for a
# new architecture is often still a PR. Gate: the built llama-server must report the resolved commit, or the build fails.
# Run it ON the build host (for .194: ssh mark@10.0.0.194 'bash -s' -- sm60 REF < build_engine.sh). Writes its PID first;
# the last line is BUILD_OK <commit> <binary path> <sha256> or the error.
# Usage: build_engine.sh sm60|gfx1201 REF [DEST_DIR]
set -euo pipefail
TARGET=${1:?usage: build_engine.sh sm60|gfx1201 REF [DEST_DIR]}; REF=${2:?usage: build_engine.sh sm60|gfx1201 REF [DEST_DIR]}
case "$TARGET" in
  sm60)    SRC=${SRC:-$HOME/llama.cpp-upstream}; BUILD=build_sm60 ;;
  gfx1201) SRC=${SRC:-/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_upstream_f74e2fa}; BUILD=build_rocm ;;
  *) echo "unknown target $TARGET (sm60 or gfx1201)"; exit 2 ;;
esac
echo $$ > "${TMPDIR:-/tmp}/build_engine_$TARGET.pid"
resolve() { git -C "$SRC" rev-parse --verify -q "$1^{commit}"; }
if [[ "$REF" == pr/* ]]; then
  git -C "$SRC" fetch -q origin "refs/pull/${REF#pr/}/head"; C=$(resolve FETCH_HEAD)
else   # a commit, tag or branch: resolve locally, else fetch and resolve THAT ref (never FETCH_HEAD, which may be anything)
  C=$(resolve "$REF" || true)
  if [ -z "$C" ]; then
    git -C "$SRC" fetch -q --tags origin; git -C "$SRC" fetch -q origin "$REF" 2>/dev/null || true
    C=$(resolve "$REF" || true)
  fi
fi
[ -n "$C" ] || { echo "ABORT: cannot resolve $REF in $SRC"; exit 1; }
S=${C:0:8}
JOBS=$(nproc); [ "$TARGET" = gfx1201 ] && JOBS=8   # the desktop: page-cache churn from a 16-way HIP build gets jobs killed
case "$TARGET" in
  sm60)    DST=${3:-$HOME/llama.cpp-$S} ;;
  gfx1201) DST=${3:-/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_$S} ;;
esac
if [ -d "$DST" ]; then
  # 2026-11-11: an existing build may be a frozen instrument's (the AbstentionBench judge runs f74e2fa build_rocm); a
  # reconfigure there recompiled it. Rebuilding in place needs REBUILD=1, and a replay of a stored arm afterwards.
  [ "${REBUILD:-0}" = 1 ] || { echo "ABORT: $DST exists; set REBUILD=1 to rebuild it in place"; exit 1; }
  [ "$(git -C "$DST" rev-parse HEAD)" = "$C" ] || { echo "ABORT: $DST exists at $(git -C "$DST" rev-parse --short HEAD), not $S"; exit 1; }
else
  git -C "$SRC" worktree add -q --detach "$DST" "$C"
fi
cd "$DST"; echo "ref $REF -> commit $C in $DST"
if [ "$TARGET" = sm60 ]; then
  cmake -B "$BUILD" -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-13 \
    -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA_FA=ON -DGGML_SCHED_MAX_COPIES=4 -DLLAMA_BUILD_TESTS=OFF > /dev/null
else
  HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" cmake -B "$BUILD" -DGGML_HIP=ON -DGPU_TARGETS=gfx1201 \
    -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA_FA=ON -DGGML_SCHED_MAX_COPIES=4 -DLLAMA_BUILD_TESTS=OFF > /dev/null
fi
cmake --build "$BUILD" -j "$JOBS" --target llama-server llama-cli llama-perplexity
B="$DST/$BUILD/bin/llama-server"
V=$("$B" --version 2>&1 | grep -m1 -o "commit [0-9a-f]*" || true)
[ -n "$V" ] && [[ "$C" == "${V#commit }"* ]] || { echo "ABORT: built server reports '${V:-no commit}', expected $S"; exit 1; }
echo "BUILD_OK $C $B $(sha256sum "$B" | cut -d' ' -f1)"
