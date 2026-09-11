#!/usr/bin/env bash
# One pelican3 rep in the foreground: a 2 s memory trace, plus run_one_p1.py under a wall-clock
# backstop. The backstop keeps a rep inside a 10-minute foreground job; generation itself is capped
# at 480 s inside the runner.
# Usage: pelican3_rep.sh ARM REP      (ARM = BASE | QWOPUS | DAVIDAU)
set -u
ROOT=/mnt/TG_2TB/Projects/Apollo
OUT=$ROOT/data/receipts/svgbench-pelican3
case "${1:-}" in
  BASE)    M=/mnt/TG_2TB/AI/Models/pelican3/Qwen3.8-27B.i1-IQ3_M.gguf ;;
  QWOPUS)  M=/mnt/TG_2TB/AI/Models/pelican3/Qwopus3.8-27B-Flash.i1-IQ3_M.gguf ;;
  DAVIDAU) M=/home/mark/Downloads/Qwen3.8-27B-TTURBO-Fable-C-Fusion-709-L-Uncen-NM-DAU-NEO-MTP-IQ3_M.gguf ;;
  *) echo "usage: $0 BASE|QWOPUS|DAVIDAU REP"; exit 2 ;;
esac
REP=${2:?rep}
mkdir -p "$OUT"
[ -f "$OUT/memtrace.csv" ] || echo "epoch,arm,rep,mem_avail_mb,swap_used_mb,gtt_used_mb,vram_used_mb" > "$OUT/memtrace.csv"
C=/sys/class/drm/card1/device
( while :; do
    a=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
    s=$(awk '/SwapTotal/{t=$2} /SwapFree/{f=$2} END{print int((t-f)/1024)}' /proc/meminfo)
    echo "$(date +%s),$1,$REP,$a,$s,$(( $(cat $C/mem_info_gtt_used)/1048576 )),$(( $(cat $C/mem_info_vram_used)/1048576 ))" >> "$OUT/memtrace.csv"
    sleep 2
  done ) &
S=$!
trap 'kill $S 2>/dev/null' EXIT
timeout -s INT 585 "$ROOT/venv_cachyos/bin/python3" "$ROOT/tools/svgbench/run_one_p1.py" "$M" "$1" "$OUT" "$REP"
rc=$?
awk -F, -v a="$1" -v r="$REP" '$2==a && $3==r { if ($7>v) v=$7; if (m=="" || $4<m) m=$4; if ($6>g) g=$6 }
  END { printf "rc=%d | peak VRAM %d MiB | peak GTT %d MiB | min MemAvailable %d MiB\n", '"$rc"', v, g, m }' "$OUT/memtrace.csv"
