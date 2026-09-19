#!/usr/bin/env bash
# Build PrismML-Eng/llama.cpp @ prism for sm_60, to run the Bonsai 2 ladder cells on .73.
#
# WHY A NEW TREE: the repo's engines/prism_llama_cpp checkout defines GGML_TYPE_COUNT = 42 and
# cannot represent Bonsai 2 at all (types 142/143). origin/prism is ~2520 commits ahead.
#
# HOST COMPILER IS PINNED TO gcc-13 ON PURPOSE. This box's default cc is gcc 15.2, and CUDA
# 12.4's host_config.h line 143 hard-errors: "gcc versions later than 13 are not supported".
# Left to the default, this build fails minutes in. gcc-13 is installed; use it.
set -uo pipefail
SRC=/home/mark/prism_llama_cpp
BUILD=$SRC/build_sm60
LOG=/home/mark/ladder/prism_build.log
mkdir -p /home/mark/ladder
: > "$LOG"

if [ ! -d "$SRC/.git" ]; then
  echo "[$(date +%H:%M:%S)] cloning prism branch (shallow)" >> "$LOG"
  git clone --depth 1 --branch prism https://github.com/PrismML-Eng/llama.cpp.git "$SRC" >> "$LOG" 2>&1 || {
    echo "CLONE_FAILED" >> "$LOG"; exit 1; }
fi

# Provenance: the exact commit this binary came from, recorded before it is built.
COMMIT=$(git -C "$SRC" rev-parse HEAD)
echo "[$(date +%H:%M:%S)] commit $COMMIT" >> "$LOG"
echo "$COMMIT" > /home/mark/ladder/prism_commit.txt

# The types must exist in THIS tree, not merely in a branch name.
if ! grep -qE 'GGML_TYPE_PTQ1_0 *= *143' "$SRC/ggml/include/ggml.h"; then
  echo "TYPE_CHECK_FAILED: PTQ1_0=143 absent from this tree" >> "$LOG"; exit 1
fi
echo "[$(date +%H:%M:%S)] type check OK: PTQ1_0=143, PQ2_0=142 present" >> "$LOG"

cmake -S "$SRC" -B "$BUILD" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=60 \
  -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-13 \
  -DCMAKE_C_COMPILER=/usr/bin/gcc-13 \
  -DCMAKE_CXX_COMPILER=/usr/bin/g++-13 \
  -DLLAMA_CURL=OFF \
  -DGGML_NATIVE=ON >> "$LOG" 2>&1
rc=$?
echo "[$(date +%H:%M:%S)] cmake configure rc=$rc" >> "$LOG"
[ $rc -ne 0 ] && { echo "CONFIGURE_FAILED" >> "$LOG"; exit 1; }

# -j4, not -j12: nvcc peaks over 1 GB per TU, and a ladder cell is running concurrently.
  # The cell is GPU-bound (0.67 cores, ~2 GB RSS -- weights live in VRAM), so CPU contention is
  # not the worry; memory is. -j4 leaves ~7 GB headroom against 13 GB available.
cmake --build "$BUILD" --target llama-perplexity -j4 >> "$LOG" 2>&1
rc=$?
echo "[$(date +%H:%M:%S)] build rc=$rc" >> "$LOG"

BIN="$BUILD/bin/llama-perplexity"
if [ -x "$BIN" ]; then
  echo "BUILD_OK $BIN $(stat -c %s "$BIN") bytes" >> "$LOG"
else
  echo "BUILD_FAILED no binary at $BIN" >> "$LOG"
  grep -iE "error|Error [0-9]" "$LOG" | tail -15 >> "$LOG"
  exit 1
fi
