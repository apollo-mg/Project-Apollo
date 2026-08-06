#!/usr/bin/env bash
# Two things Tom asked for on #249, on the RX 9070 XT (gfx1201, HIP arch 1300), ROCm 7.2.4:
#
#   1. Confirmation run of current head 75a24b8f2 -- should match my revert-arm numbers
#      (7604 OK / 0 FAIL / 0 no-device-code, dying later in ..._tile on hsk=576).
#   2. test/hip-vec-turbo-only (418b1759c) with GRAPHS ON: does the capture abort appear on the
#      TILE path once quantized KV stops being forced to VEC? If it does, the branch trades
#      Chris's perf bug for a crash bug.
#
# WHY GRAPHS-ON IS RUN ON *BOTH* COMMITS: FLASH_ATTN_EXT already aborts under graph capture on
# 55580fe0c ("operation not permitted when stream is capturing", ggml-cuda.cu:108). So a
# graphs-on abort on the test branch proves nothing on its own -- it needs the same-session
# baseline to say whether the branch CHANGED anything. Without arm 2 this experiment cannot
# answer the question it was asked.
#
# COUNTING DISCIPLINE (both learned the hard way today):
#   - test-backend-ops colours verdicts, so `grep -c '\bOK\b'` silently returns 0 (the ANSI
#     'm' before 'OK' kills the word boundary). Everything here strips ANSI first.
#   - "0 errors" is NOT a pass: a build failure or an early abort also yields 0. Every arm
#     reports POSITIVE evidence (OK count, and the verdicts for ratio 9 specifically) so a
#     zero can never be mistaken for success.
set -u
SRC=/mnt/TG_2TB/tmp_pr244
SP=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
LOG=$SP/tq249.log
: > "$LOG"
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
strip(){ sed -r 's/\x1B\[[0-9;]*[mK]//g' "$1"; }

report(){   # $1 = arm tag, $2 = log file, $3 = rc
	local tag=$1 f=$2 rc=$3
	local ok fail ndc nsup cap last abrt r9ok
	ok=$(strip "$f"   | grep -cE ": OK$")
	fail=$(strip "$f" | grep -cE ": FAIL$")
	ndc=$(strip "$f"  | grep -c "no device code")
	nsup=$(strip "$f" | grep -c "not supported")
	cap=$(strip "$f"  | grep -c "stream is capturing")
	r9ok=$(strip "$f" | grep "nr23=\[9,1\]" | grep -cE ": OK$")
	last=$(strip "$f" | grep "FLASH_ATTN_EXT(" | tail -1 | grep -oE "hsk=[0-9]+,hsv=[0-9]+,nh=[0-9]+,nr23=\[[0-9,]+\]")
	abrt=$(strip "$f" | grep -oE "ggml_cuda_flash_attn_ext_[a-z_0-9]+" | head -1)
	say "  $tag: rc=$rc OK=$ok FAIL=$fail no-device-code=$ndc not-supported=$nsup capture-abort=$cap"
	say "      ratio-9 OK=$r9ok | last descriptor: ${last:-none} | abort in: ${abrt:-n/a}"
}

run_fa(){   # $1 = arm tag, $2 = graphs on|off
	local tag=$1 graphs=$2
	local f=$SP/tq249_${tag}.log
	local env=""
	[ "$graphs" = off ] && env="GGML_CUDA_DISABLE_GRAPHS=1"
	say "--- FLASH_ATTN_EXT  [$tag]  graphs=$graphs ---"
	( cd "$SRC/build_hip/bin" && env LD_LIBRARY_PATH=. $env timeout 1700 \
		./test-backend-ops test -o FLASH_ATTN_EXT -b ROCm0 ) > "$f" 2>&1
	report "$tag" "$f" "$?"
}

build_at(){  # $1 = ref, $2 = label
	say "########## checkout $2 ($1) ##########"
	git -C "$SRC" checkout -q --detach "$1" 2>&1 | tail -2 | tee -a "$LOG"
	say "  HEAD: $(git -C "$SRC" log --oneline -1)"
	say "  gqa form -> volta:$(git -C "$SRC" show HEAD:ggml/src/ggml-cuda/fattn.cu | sed -n '69p' | grep -oE '% 8 == 0|> 4')  non-volta:$(git -C "$SRC" show HEAD:ggml/src/ggml-cuda/fattn.cu | sed -n '92p' | grep -oE '% 8 == 0|> 4')"
	if ! make -C "$SRC/build_hip" test-backend-ops -j"$(nproc)" > "$SP/tq249_build_$2.log" 2>&1; then
		say "  BUILD FAILED:"
		grep -E "error:" "$SP/tq249_build_$2.log" | grep -v hipError_t | head -4 | sed 's/^/      /' | tee -a "$LOG"
		return 1
	fi
	say "  build ok"
	return 0
}

say "===== #249 verification on RX 9070 XT / gfx1201 / ROCm 7.2.4 ====="

if build_at 75a24b8f2 head; then
	run_fa "head_graphsoff" off
	run_fa "head_graphson"  on
else
	say "SKIPPING head arms -- build failed"
fi

if build_at 418b1759c testbranch; then
	run_fa "branch_graphson"  on
	run_fa "branch_graphsoff" off
else
	say "SKIPPING branch arms -- build failed"
fi

say "===== DONE ====="
say "READ: (1) head_graphsoff should show OK~7604, ndc=0 -> confirms the fix."
say "      (2) branch_graphson vs head_graphson: if capture-abort appears/moves to the TILE"
say "          path only on the branch, the branch introduces a crash. If both abort"
say "          identically, the capture bug is pre-existing and orthogonal."
