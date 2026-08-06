#!/usr/bin/env bash
# Decisive single-variable A/B for the RDNA4 FLASH_ATTN_EXT "no device code" failures.
#
# THE CLAIM UNDER TEST: TheTom's f924ee29f changed the non-Volta ncols2 selection in
# ggml_cuda_flash_attn_ext_mma_f16_switch_ncols2 from comparison (gqa_ratio > 4/2/1) to modulo
# (gqa_ratio % 8/4/2 == 0). For gqa_ratio = 9 the modulo form matches nothing, so ncols2 falls
# through to 1 -- and fattn-mma-f16.cuh:1981 rejects ncols2 == 1 under AMD_WMMA_AVAILABLE with
# NO_DEVICE_CODE. Old form: 9 > 4 -> ncols2 = 8, which compiles.
#
# WHY THIS DESIGN AND NOT "BUILD THE PARENT COMMIT": the parent (e1fd6cea3) does not compile at
# all -- src/llama-model.h declares LLM_TYPE_118B_A8B twice and src/models/models.h defines
# struct llama_model_laguna twice. Both duplications are still present at f924ee29f and are only
# fixed later, so there is no clean pre-GQA commit to build. Reverting the 3-line hunk on top of
# the adopted head (55580fe0c) is strictly better anyway: ONE variable changes, everything else
# -- compiler, flags, ROCm, every other fork patch -- is held byte-identical.
#
# CONTROL: the head binaries were copied to bin_head BEFORE the revert, so both arms run in the
# same session, on the same GPU, at the same clocks. The earlier head result (23 failures) is
# NOT reused as the control -- it is re-measured here.
#
# GRAPHS: FLASH_ATTN_EXT aborts under HIP graph capture ("operation not permitted when stream is
# capturing", ggml-cuda.cu:108) on BOTH arms -- that is a separate defect, Tom's #247 class, and
# it masks the thing being measured. GGML_CUDA_DISABLE_GRAPHS=1 is set for both arms to get past
# it. Disabling graphs is therefore part of the measurement, not a fix.
set -u
SP=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
SRC=/mnt/TG_2TB/tmp_pr244
LOG=$SP/gqa_ab.log
: > "$LOG"
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

say "===== GQA ncols2 A/B on gfx1201 (RX 9070 XT) ====="
say "head   = 55580fe0c as built (modulo)   -> $SP/bin_head"
say "revert = 55580fe0c minus f924ee29f's fattn.cu hunk (comparison)"
say "gpu: $(rocm-smi --showproductname 2>/dev/null | grep -i 'card series' | head -1 | sed 's/^ *//')"

# ---- build the revert arm ------------------------------------------------------------------
say "building revert arm (incremental; only fattn.cu should recompile)..."
if ! make -C "$SRC/build_hip" test-backend-ops -j"$(nproc)" > "$SP/gqa_revert_build.log" 2>&1; then
	say "BUILD FAILED -- last real errors:"
	grep -E "error:" "$SP/gqa_revert_build.log" | grep -v hipError_t | head -5 | sed 's/^/    /' | tee -a "$LOG"
	say "ABORTING: cannot compare arms when one did not build."
	exit 1
fi
say "build ok. binary mtime: $(stat -c %y "$SRC/build_hip/bin/test-backend-ops" | cut -d. -f1)"

# $1 = arm tag, $2 = directory holding test-backend-ops + its .so files
run_arm(){
	local tag=$1 dir=$2
	local out=$SP/gqa_${tag}_fa.log
	say "########## ARM $tag  ($dir) ##########"
	( cd "$dir" && LD_LIBRARY_PATH=. GGML_CUDA_DISABLE_GRAPHS=1 \
		timeout 1700 ./test-backend-ops test -o FLASH_ATTN_EXT -b ROCm0 ) > "$out" 2>&1
	local rc=$?
	local ndc ok fail
	ndc=$(grep -ac "no device code" "$out")
	ok=$(grep -ac "\bOK\b" "$out")
	fail=$(grep -acE "\bFAIL\b" "$out")
	say "  rc=$rc  no-device-code=$ndc  OK-lines=$ok  FAIL-lines=$fail"
	if [ "$ndc" -gt 0 ]; then
		say "  distinct failing shapes:"
		grep -B1 "no device code" "$out" | grep -oE "nh=[0-9]+,nr23=\[[0-9]+,[0-9]+\]" \
			| sort -u | head -20 | sed 's/^/      /' | tee -a "$LOG"
	fi
	say "  tail:"
	tail -3 "$out" | sed 's/^/    | /' | tee -a "$LOG"
}

run_arm "revert" "$SRC/build_hip/bin"
run_arm "head"   "$SP/bin_head"

say "===== DONE ====="
say "READ: attribution confirmed only if revert=0 AND head>0. Any other pattern means the"
say "      3-line hunk is not the cause and the report must not be sent."
