#!/usr/bin/env bash
# Is buun's 6.1x RDNA4 slowdown a REGRESSION or longstanding?
#
# Today (fork HEAD 7939b6c47) buun runs the f16 perplexity base ~6.1x slower than TheTom's
# fork on gfx1201 -- flat across f16 and turbo4, immune to TURBO_MEANSUB_OFF and
# TURBO_FUSED_PREFILL. Build configs of both forks are identical (Release, -O3 -DNDEBUG,
# gfx1201, GGML_HIP=ON) so it is not a build artifact.
#
# Mark surfaced the 2026-07-23 RDNA4 unroll A/B, whose staged worktree wt-master sits at
# 58364703a -- roughly 200 commits BEHIND today's HEAD -- and has a working llama-perplexity.
# On that commit buun's fork benched Bonsai-8B at 36.45 t/s DECODE, which looked healthy.
# Decode-t/s and prefill-wall-time are different measurements, so that is not a contradiction;
# it is an opportunity: run TODAY's exact test on the OLD build.
#
#   old fast + new slow -> regression inside a ~200-commit window, bisectable. Far more
#                          actionable for buun than "RDNA4 is slow".
#   old slow            -> longstanding RDNA4 gap; the report stands as written.
set -u
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/27B/Qwopus3.5-27B-v3-Q2_K.gguf"
DATASET=/home/mark/wikitext-2-raw/wiki.test.raw
OUT=/home/mark/projects/HermesAgent-20/buun_isolate
LOG=$OUT/regression.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
# guard against the placeholder-corpus trap that voided the 2026-07-23 PPL leg
sz=$(stat -c%s "$DATASET" 2>/dev/null || echo 0)
[ "$sz" -lt 100000 ] && { say "ABORT: dataset only $sz bytes -- placeholder, not wikitext-2"; exit 1; }
say "dataset ok ($sz bytes)"

run() {
	local tag=$1 bin=$2 kv=$3 rep=$4
	local lg=$OUT/logs/reg_${tag}_${kv}_r${rep}.log
	mkdir -p "$OUT/logs"
	local t0; t0=$(date +%s)
	LD_LIBRARY_PATH="$bin" "$bin/llama-perplexity" -m "$MODEL" -f "$DATASET" \
		-ctk "$kv" -ctv "$kv" -fa on -c 2048 --chunks 2 -ngl 99 > "$lg" 2>&1
	local rc=$?; local t1; t1=$(date +%s)
	local ppl; ppl=$(grep -m1 "Final estimate: PPL" "$lg" | sed 's/.*= *//' | awk '{print $1}')
	if [ $rc -ne 0 ] || [ -z "$ppl" ]; then
		say "  $tag/$kv r$rep FAILED rc=$rc"; grep -iE "error|unsupported|fault" "$lg" | tail -2 | sed 's/^/      /' | tee -a "$LOG"
	else
		say "  $tag/$kv r$rep  $((t1-t0))s  PPL=$ppl"
	fi
}

OLD=/mnt/TG_2TB/tmp_rdna4_ab/wt-master/build/bin
NEW=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build/bin
TOM=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin
say "=== REGRESSION CHECK: buun 58364703a (Jul 23) vs 7939b6c47 (today) vs Tom ==="
for rep in 1 2; do
	run tom_ref  "$TOM" f16 "$rep"
	run buun_old "$OLD" f16 "$rep"
	run buun_new "$NEW" f16 "$rep"
	run buun_old "$OLD" turbo4 "$rep"
	run buun_new "$NEW" turbo4 "$rep"
done
say "=== DONE ==="
