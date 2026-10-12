#!/usr/bin/env bash
# One Turbo-Brilliance pelican rep in the foreground: a 2 s memory trace, plus run_tb_p1.py under a wall-clock
# backstop (generation itself is capped at 480 s inside the runner). Same shape as pelican3_rep.sh.
# Usage: tb_rep.sh ARM REP      (ARM = CTRL | CODER | QUINN | OMNI)
set -u
ROOT=/mnt/TG_2TB/Projects/Apollo
OUT=$ROOT/data/receipts/svgbench-turbobrilliance
case "${1:-}" in CTRL|CODER|QUINN|OMNI) ;; *) echo "usage: $0 CTRL|CODER|QUINN|OMNI REP"; exit 2 ;; esac
REP=${2:?rep}
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
timeout -s INT 585 "$ROOT/venv_cachyos/bin/python3" "$ROOT/tools/svgbench/run_tb_p1.py" "$1" "$REP"
rc=$?
awk -F, -v a="$1" -v r="$REP" '$2==a && $3==r { if ($7>v) v=$7; if (m=="" || $4<m) m=$4; if ($6>g) g=$6 }
  END { printf "rc=%d | peak VRAM %d MiB | peak GTT %d MiB | min MemAvailable %d MiB\n", '"$rc"', v, g, m }' "$OUT/memtrace.csv"
