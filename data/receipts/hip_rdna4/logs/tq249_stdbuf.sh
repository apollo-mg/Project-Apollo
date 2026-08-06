#!/usr/bin/env bash
# Re-run the two graphs-ON arms under stdbuf -o0 (line-buffered stdout).
# WHY: both arms abort, and test-backend-ops block-buffers descriptors to stdout while errors go
# unbuffered to stderr -- so on death the last descriptors are LOST and the OK counts are
# truncated by however much was still in the buffer. The head-vs-branch gap (3007 vs 898) is the
# claim being reported to the maintainer, so it must not rest on a buffering artifact.
set -u
SRC=/mnt/TG_2TB/tmp_pr244
SP=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
strip(){ sed -r 's/\x1B\[[0-9;]*[mK]//g' "$1"; }
run(){ # $1 tag
	local f=$SP/sb_$1.log
	( cd "$SRC/build_hip/bin" && stdbuf -o0 -e0 env LD_LIBRARY_PATH=. timeout 900 \
		./test-backend-ops test -o FLASH_ATTN_EXT -b ROCm0 ) > "$f" 2>&1
	local rc=$?
	echo "  $1: rc=$rc OK=$(strip "$f" | grep -cE ': OK$') capture=$(strip "$f" | grep -c 'stream is capturing')"
	echo "     LAST TEST LINE: $(strip "$f" | grep 'FLASH_ATTN_EXT(' | tail -1 | cut -c1-155)"
	echo "     abort site: $(strip "$f" | grep -oE 'ggml_cuda_flash_attn_ext_[a-z_0-9]+|ggml-cuda.cu:[0-9]+' | head -2 | tr '\n' ' ')"
}
echo "=== branch 418b1759c, graphs ON (stdbuf) ==="; run branch_on
git -C "$SRC" checkout -q --detach 75a24b8f2
make -C "$SRC/build_hip" test-backend-ops -j"$(nproc)" > /dev/null 2>&1 || { echo "BUILD FAILED"; exit 1; }
echo "=== head 75a24b8f2, graphs ON (stdbuf) ==="; run head_on
