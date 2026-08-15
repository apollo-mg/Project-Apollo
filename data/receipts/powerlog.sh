#!/usr/bin/env bash
# Sample GPU power continuously so throughput comparisons can be read per watt.
#
# WHY. Two arms with the same t/s and different draw differ structurally, and on
# power-capped hardware the cap can clip an advantage that would appear on an
# uncapped card. The P100 fleet runs a 150 W cap (standing config since
# 2026-07-17), so an arm that saturates it is being throttled and further
# optimisation of that arm buys nothing -- which is invisible in a t/s column.
#
# Batched drafting (DFlash, one pass over a block) should occupy the GPU better
# than sequential drafting (MTP, n passes of one token) and therefore draw more.
# Higher draw is CONFIRMATION of the mechanism, not a cost -- unless it hits a cap.
#
# Note that "% GPU busy" is time-busy, not occupancy: a GPU dribbling one token at
# a time reads 100 % while using a fraction of its width. Power does not lie the
# same way, which is why this samples watts rather than utilisation.
#
# Usage:
#   powerlog.sh <outfile> [interval_s]     # sample until killed
#   benches append markers themselves:
#       echo "MARK $(date +%s) <tag> start" >> <outfile>
#       echo "MARK $(date +%s) <tag> end"   >> <outfile>
#   then: power_merge.py <outfile>
set -u
OUT=${1:?usage: powerlog.sh <outfile> [interval_s]}
IV=${2:-1}

if command -v rocm-smi >/dev/null 2>&1; then
    VENDOR=amd
elif command -v nvidia-smi >/dev/null 2>&1; then
    VENDOR=nvidia
else
    echo "no rocm-smi or nvidia-smi on PATH" >&2; exit 1
fi

echo "# vendor=$VENDOR interval=${IV}s host=$(hostname) start=$(date -Is)" >> "$OUT"

# Record the cap once -- an arm at the cap is throttled, and that changes the read.
if [ "$VENDOR" = nvidia ]; then
    cap=$(nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits 2>/dev/null | paste -sd, -)
    echo "# power_limit_w=$cap" >> "$OUT"
fi

while true; do
    t=$(date +%s)
    if [ "$VENDOR" = amd ]; then
        rocm-smi --showpower --csv 2>/dev/null \
          | awk -F, -v t="$t" 'NR>1 && $2 ~ /[0-9]/ {printf "%s,%s,%s\n", t, $1, $2}' >> "$OUT"
    else
        nvidia-smi --query-gpu=index,power.draw --format=csv,noheader,nounits 2>/dev/null \
          | awk -F", *" -v t="$t" '{printf "%s,gpu%s,%s\n", t, $1, $2}' >> "$OUT"
    fi
    sleep "$IV"
done
