#!/usr/bin/env bash
# turbo4 stability on RDNA4 — self-validating repro for buun's fork.
#
# WHAT THIS TESTS
# On a RX 9070 XT (gfx1201), buun-llama-cpp @ 7939b6c47, Qwopus3.5-27B-v3-Q2_K:
#   turbo4 KV : 2/22 runs hard NaN (~9%); the 11 finite runs spanned PPL 8.0984-8.1825,
#               EVERY ONE DIFFERENT (spread 0.0841)
#   f16 KV    : bit-stable, 7.4948 every single run, same fork same card
#   Tom's fork: turbo4 bit-stable, 7.4880 every run
# So the instability is specific to the turbo decode path in this fork.
#
# WHY f16 IS RUN TOO, AND WHY IT MATTERS
# The f16 arm is not padding -- it is the control that makes the turbo4 result mean anything.
# llama-perplexity is a deterministic harness (no prompt cache, no continuous batching), and
# f16 being bit-identical across N runs PROVES that on YOUR machine, in THIS session, before
# you look at turbo4 at all. If f16 also drifts, stop: the problem is the box or the build,
# not the codec, and any turbo4 number you take is meaningless.
# Read the arms in that order. The comparison is the evidence; neither arm alone is.
#
# NOTE: perplexity is NOT affected by the llama-server determinism gotcha (-cb / cache_prompt).
# That one applies to server benchmarking, not here.
#
# NaN DETECTION IS ON OUTPUT, NOT EXIT CODE. The NaN run exits 0 and prints
# "Unexpected negative standard deviation of log(prob)" to stderr. Anything checking $? misses
# it entirely -- that is how it went unnoticed. We detect a MISSING "Final estimate" or a
# literal nan in the log.
#
# USAGE
#   BIN=/path/to/build/bin MODEL=/path/to/model.gguf DATASET=/path/to/wiki.test.raw \
#     ./turbo4_stability.sh
#   optional: N=12 (reps per arm)  REF_BIN=/path/to/other/fork/build/bin (cross-fork control)
set -u
BIN=${BIN:?set BIN to the build/bin dir of the fork under test}
MODEL=${MODEL:?set MODEL to a .gguf}
DATASET=${DATASET:?set DATASET to wikitext-2 wiki.test.raw}
REF_BIN=${REF_BIN:-}
N=${N:-12}
OUT=${OUT:-./turbo4_stability_out}
mkdir -p "$OUT/logs"
LOG=$OUT/report.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

# Guard against the placeholder-corpus trap: a truncated wiki.test.raw silently voids a whole
# PPL leg. Real wikitext-2 test is ~1.3 MB.
sz=$(stat -c%s "$DATASET" 2>/dev/null || echo 0)
[ "$sz" -lt 100000 ] && { echo "ABORT: dataset only $sz bytes — placeholder, not wikitext-2"; exit 1; }

arm() {
	local tag=$1 bin=$2 kv=$3
	local nan=0 ok=0 i
	say "--- arm: $tag  (-ctk $kv -ctv $kv)  x$N ---"
	for i in $(seq 1 "$N"); do
		local lg=$OUT/logs/${tag}_${kv}_r${i}.log
		LD_LIBRARY_PATH="$bin" "$bin/llama-perplexity" -m "$MODEL" -f "$DATASET" \
			-ctk "$kv" -ctv "$kv" -fa on -c 2048 --chunks 2 -ngl 99 > "$lg" 2>&1
		local ppl; ppl=$(grep -m1 "Final estimate: PPL" "$lg" | sed 's/.*= *//' | awk '{print $1}')
		if [ -z "$ppl" ] || grep -qi "nan" "$lg"; then
			nan=$((nan+1)); say "  rep $i  *** NaN/FAIL ***"
		else
			ok=$((ok+1)); say "  rep $i  PPL=$ppl"; echo "$ppl" >> "$OUT/${tag}_${kv}.vals"
		fi
	done
	local summary
	summary=$(sort -n "$OUT/${tag}_${kv}.vals" 2>/dev/null | awk -v n="$nan" -v t="$N" '
		{a[NR]=$1}
		END{
			if(NR==0){printf "ALL %d RUNS FAILED", t; exit}
			d=(NR>1)?a[NR]-a[1]:0
			printf "NaN %d/%d | finite %d | min=%s max=%s spread=%.4f | %s",
				n, t, NR, a[1], a[NR], d, (d==0 && n==0)?"BIT-STABLE":"UNSTABLE"
		}')
	say "  => $tag/$kv: $summary"
	echo "$tag/$kv|$summary" >> "$OUT/summary.txt"
}

rm -f "$OUT"/*.vals "$OUT/summary.txt"
say "=== turbo4 stability, N=$N per arm ==="
say "bin    : $BIN"
say "model  : $MODEL"
say "dataset: $DATASET ($sz bytes)"

# CONTROL FIRST. If this arm is not bit-stable, nothing below it is interpretable.
arm under_test "$BIN" f16
arm under_test "$BIN" turbo4

if [ -n "$REF_BIN" ]; then
	say "--- cross-fork reference ---"
	arm reference "$REF_BIN" f16
	arm reference "$REF_BIN" turbo4
fi

say ""
say "=== SUMMARY ==="
cat "$OUT/summary.txt" | tee -a "$LOG"
say ""
say "READ IT LIKE THIS:"
say "  f16 BIT-STABLE + turbo4 UNSTABLE  -> reproduces the reported bug; it is the turbo path"
say "  f16 UNSTABLE                      -> your box/build is the variable; turbo4 numbers void"
say "  both BIT-STABLE                   -> does NOT reproduce here; report build + card"
say "=== DONE ==="
