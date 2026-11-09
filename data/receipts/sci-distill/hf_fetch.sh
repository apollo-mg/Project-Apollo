#!/usr/bin/env bash
# Pinned Hugging Face download for PREREG_SCI_DISTILL.md (Mark's OK, 2026-11-09). Files from LIST ("path size sha256",
# "-" = not an LFS file: size check only), from REPO at full revision REV. Two lanes, resumable: rerun to continue;
# verified files are skipped; a mismatch -> .bad. DEST/download.log ends "ALL OK" or "FAILED <n>".
# Usage: hf_fetch.sh REPO REV LIST DEST
set -u
REPO=${1:?}; REV=${2:?}; LIST=${3:?}; DEST=${4:?}
mkdir -p "$DEST"; LOG="$DEST/download.log"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
need=0; while read -r p s h; do [ -e "$DEST/$p.verified" ] || need=$((need + s)); done < "$LIST"
free=$(df --output=avail -B1 "$DEST" | tail -1); log "start $REPO@$REV: need up to $need bytes, free $free"
[ "$free" -gt $((need + 20000000000)) ] || { log "FAILED disk"; exit 1; }
lane() {
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
