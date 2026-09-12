#!/bin/bash
# sm_60 qualification build for buun 4d90517b1 "cuda: restore Pascal builds for native quantization".
#
# Builds in a FRESH git worktree so no existing checkout or build dir on .73 is disturbed, and so the
# superseded LOCAL_PATCH_sm60_guards.diff cannot contaminate the result -- buun's upstream guards are
# what we are qualifying.
#
# Deliberately does NOT run the test binary. Both P100s are serving a VBR-armed llama-server with
# ~2 GB VRAM free; a CUDA test allocating there can make the VBR controller degrade its KV tier
# mid-serve. The run is a separate, explicitly-approved step.
#
# nice -j4 rather than -j12: the box has 15 GB RAM and a live llama-server plus an interactive desktop.
set -u
REPO=$HOME/buun-llama-cpp
WT=$HOME/buun-sm60-qual
BUILD=$WT/build_sm60qual
LOG=$HOME/sm60_qual.log
PIDF=$HOME/sm60_qual.pid

say () { echo "$(date '+%F %T') $*" >> "$LOG"; }

echo $$ > "$PIDF"
: > "$LOG"
say "=== sm_60 qualification build ==="
say "host: $(hostname)  nproc: $(nproc)  cuda: $(nvcc --version 2>/dev/null | tail -1)"
say "driver: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)"
say "NOTE: buun validated with CUDA 12.8; this box has the above. A toolkit difference is a real"
say "      variable and must be stated in any report back to him."

cd "$REPO" || { say "FATAL: no $REPO"; exit 1; }
say "fetching origin"
git fetch origin >> "$LOG" 2>&1 || { say "FATAL: fetch failed"; exit 1; }
TARGET=$(git rev-parse origin/master)
say "origin/master = $TARGET"

if [ -d "$WT" ]; then
  say "reusing worktree $WT"
  ( cd "$WT" && git checkout --detach "$TARGET" ) >> "$LOG" 2>&1 || { say "FATAL: checkout failed"; exit 1; }
else
  say "creating worktree $WT"
  git worktree add --detach "$WT" "$TARGET" >> "$LOG" 2>&1 || { say "FATAL: worktree add failed"; exit 1; }
fi

cd "$WT" || { say "FATAL: no $WT"; exit 1; }
say "worktree HEAD: $(git log --oneline -1)"
NMOD=$(git status --porcelain | grep -v '^??' | wc -l)
say "tracked files modified in worktree: $NMOD  (MUST be 0 -- our local sm60 patch must not be here)"
if git merge-base --is-ancestor 4d90517b1 HEAD 2>/dev/null; then
  say "contains 4d90517b1 (Pascal restore): YES"
else
  say "contains 4d90517b1 (Pascal restore): NO -- ABORTING, wrong tree"; exit 1
fi

say "configuring (sm_60 only, tests on)"
cmake -B "$BUILD" \
  -DGGML_CUDA=ON \
  -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
  -DGGML_CUDA_FA=ON \
  -DGGML_CUDA_FA_ALL_QUANTS=OFF \
  -DCMAKE_CUDA_ARCHITECTURES=60 \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLAMA_BUILD_TESTS=ON >> "$LOG" 2>&1
if [ $? -ne 0 ]; then say "CONFIGURE FAILED"; exit 1; fi
say "configure OK"

say "--- building target test-exl3-byte-dot (his new regression) ---"
S=$(date +%s)
nice -n 15 cmake --build "$BUILD" -j4 --target test-exl3-byte-dot >> "$LOG" 2>&1
RC=$?
say "test-exl3-byte-dot build rc=$RC  elapsed=$(( ($(date +%s) - S) / 60 )) min"
if [ $RC -ne 0 ]; then
  say "BUILD FAILED -- this is itself a reportable result for buun. Not attempting llama-server."
  say "=== FINISHED (failure) ==="
  exit 1
fi

say "--- building target llama-server (the full SM60 server build) ---"
S=$(date +%s)
nice -n 15 cmake --build "$BUILD" -j4 --target llama-server >> "$LOG" 2>&1
RC2=$?
say "llama-server build rc=$RC2  elapsed=$(( ($(date +%s) - S) / 60 )) min"

say "--- artefacts ---"
ls -la "$BUILD/bin/test-exl3-byte-dot" "$BUILD/bin/llama-server" >> "$LOG" 2>&1
say "=== FINISHED. Test binary deliberately NOT executed (VRAM/VBR conflict with the live server). ==="
