#!/usr/bin/env bash
# Speed A/B for buun aad850104 against OLD 3823c9eb6 and FIX a334fc01e. PREREG_SPEED_AAD85.md.
# Resumable: a run whose .md exists is skipped. Stops launching new runs once MAX seconds have
# passed, so each call fits a 10-minute foreground job.
# Usage: speed_ab_aad85.sh [MAX_SECONDS]
set -u
OUT=/mnt/TG_2TB/Projects/Apollo/data/receipts/viability/fix-ab/bench_aad85
M=/mnt/TG_2TB/AI/Models/gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf
declare -A BIN=( [OLD]=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin/llama-bench
                 [FIX]=/mnt/TG_2TB/Projects/buun-master/build_rocm/bin/llama-bench
                 [NEW]=/mnt/TG_2TB/Projects/buun-aad85/build_rocm/bin/llama-bench )
declare -A CFG=( [E]="-ctk f16 -ctv f16 -p 512 -n 128 -r 3"
                 [F]="-ctk f16 -ctv f16 -p 0 -n 128 -d 13000 -r 2"
                 [V]="-ctk vbr -ctv vbr -p 0 -n 128 -d 13000 -r 2" )
ORDER=("1 OLD" "1 FIX" "1 NEW" "2 NEW" "2 FIX" "2 OLD")
MAX=${1:-480}; T0=$(date +%s)
mkdir -p "$OUT"
if [ ! -f "$OUT/env.txt" ]; then
  { echo "date $(date '+%F %T')"
    echo "cap $(( $(cat /sys/class/drm/card1/device/hwmon/hwmon*/power1_cap) / 1000000 )) W"
    echo "OLD 3823c9eb6  FIX a334fc01e  NEW aad850104"
    echo "model $M"
    for c in E F V; do echo "cfg $c: -ngl 99 -fa 1 ${CFG[$c]}"; done; } > "$OUT/env.txt"
fi
for o in "${ORDER[@]}"; do
  set -- $o; r=$1; b=$2
  for c in E F V; do
    f="$OUT/${b}_${c}_${r}"
    [ -s "$f.md" ] && continue
    if [ $(( $(date +%s) - T0 )) -ge "$MAX" ]; then echo "chunk budget reached; rerun the same command to resume"; exit 3; fi
    if pgrep -x llama-server >/dev/null; then echo "a llama-server is running -- refusing to benchmark"; exit 2; fi
    echo "$(date +%T) $b $c round $r"
    if "${BIN[$b]}" -m "$M" -ngl 99 -fa 1 ${CFG[$c]} -o md > "$f.md.tmp" 2> "$f.err"; then
      mv "$f.md.tmp" "$f.md"
      grep -E "tg128|pp512" "$f.md" | awk -F'|' '{printf "   %s %s\n", $(NF-2), $(NF-1)}'
    else
      echo "   FAILED rc=$? (see $f.err)"; rm -f "$f.md.tmp"
    fi
  done
done
echo "ALL_DONE"
