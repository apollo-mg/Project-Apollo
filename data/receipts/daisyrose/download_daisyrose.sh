#!/usr/bin/env bash
# DaisyRose-27B (RadixArk, BF16, RL-only fine-tune of Qwen3.8-27B) for M1 + agent runs (Mark's OK, 2026-11-21), pinned to revision 64a4ec66.
# Files from files.txt (path size sha256; "-" = not an LFS file: size check only).
# Two lanes, resumable: rerun to continue; verified files are skipped; a mismatch -> .bad, FAILED.
# Usage: download_daisyrose.sh DEST_DIR    (DEST_DIR/download.log ends "ALL OK" or "FAILED <n>")
echo $$ > /tmp/download_daisyrose.pid
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; DEST=${1:?usage: download_daisyrose.sh DEST_DIR}
REPO=RadixArk/DaisyRose-27B; REV=64a4ec665091bb0c1931babce4e97e686eef3c5c
mkdir -p "$DEST"; LOG="$DEST/download.log"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
LIST="$HERE/files.txt"
need=0; while read -r p s h; do f="$DEST/$p"; [ -e "$f.verified" ] || need=$((need + s)); done < "$LIST"
free=$(df --output=avail -B1 "$DEST" | tail -1); log "start: need up to $need bytes, free $free"
[ "$free" -gt $((need + 20000000000)) ] || { log "FAILED disk"; exit 1; }
lane() {   # lane N: every other line
  local bad=0 i=0
  while read -r p s h; do
    i=$((i + 1)); [ $((i % 2)) = "$1" ] || continue
    local f="$DEST/$p"; [ -e "$f.verified" ] && continue
    curl -fsSL --retry 30 --retry-delay 15 --retry-all-errors -C - -o "$f" "https://huggingface.co/$REPO/resolve/$REV/$p" \
      || { log "CURL-FAIL $p"; bad=$((bad + 1)); continue; }
    [ "$(stat -c %s "$f")" = "$s" ] || { log "SIZE-MISMATCH $p"; mv "$f" "$f.bad"; bad=$((bad + 1)); continue; }
    if [ "$h" != "-" ]; then
      [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$h" ] || { log "SHA-MISMATCH $p"; mv "$f" "$f.bad"; bad=$((bad + 1)); continue; }
    fi
    echo "$h" > "$f.verified"; log "OK $p"
  done < "$LIST"
  echo $bad > "$DEST/lane$1.bad"
}
lane 0 & lane 1 & wait
n=$(( $(cat "$DEST/lane0.bad") + $(cat "$DEST/lane1.bad") )); [ "$n" = 0 ] && log "ALL OK" || log "FAILED $n"
