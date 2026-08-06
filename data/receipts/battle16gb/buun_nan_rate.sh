#!/usr/bin/env bash
# How often does buun's turbo4 decode go NaN / drift on RDNA4?
#
# Today: 10 turbo4 runs on the current build produced 9 finite PPLs spanning 8.0955-8.4805
# and 1 hard NaN ([1]nan,[2]nan -> "Unexpected negative standard deviation of log(prob)").
# f16 on the same fork is bit-stable (7.4948 every time) and Tom's turbo4 is bit-stable
# (7.4880 every time). So the instability is specific to buun's turbo decode path here.
#
# 1/10 is not a rate. This runs N stock turbo4 reps to (a) estimate the NaN frequency and
# (b) measure the spread of the finite values, which together tell buun whether he is chasing
# a rare edge case or a path that is broadly nondeterministic.
#
# NOTE ON EXIT CODES: the NaN run exited 0 and printed its error to stderr, so an rc check
# misses it. Detection here is on the OUTPUT (missing "Final estimate" or literal nan).
set -u
BIN=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build/bin
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/27B/Qwopus3.5-27B-v3-Q2_K.gguf"
DATASET=/home/mark/wikitext-2-raw/wiki.test.raw
OUT=/home/mark/projects/HermesAgent-20/buun_isolate/nanrate
N=${N:-12}
mkdir -p "$OUT"
LOG=$OUT/nanrate.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
say "=== turbo4 stability: $N stock reps, current build ==="
nan=0; ok=0
for i in $(seq 1 "$N"); do
	lg=$OUT/run_$i.log
	LD_LIBRARY_PATH="$BIN" "$BIN/llama-perplexity" -m "$MODEL" -f "$DATASET" \
		-ctk turbo4 -ctv turbo4 -fa on -c 2048 --chunks 2 -ngl 99 > "$lg" 2>&1
	ppl=$(grep -m1 "Final estimate: PPL" "$lg" | sed 's/.*= *//' | awk '{print $1}')
	if [ -z "$ppl" ] || grep -q "nan" "$lg"; then
		nan=$((nan+1)); say "  rep $i  *** NaN/FAIL ***"
	else
		ok=$((ok+1)); say "  rep $i  PPL=$ppl"
	fi
done
say "--- NaN $nan / $N ; finite $ok ---"
grep -oE "PPL=[0-9.]+" "$LOG" | sed 's/PPL=//' | sort -n | awk '
  {a[NR]=$1} END{if(NR)printf "finite PPL: min=%s max=%s spread=%.4f over %d runs\n",a[1],a[NR],a[NR]-a[1],NR}' | tee -a "$LOG"
say "=== DONE ==="
