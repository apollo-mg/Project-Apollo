#!/usr/bin/env bash
# Matched Sage rerun (PREREG_SAGE_MATCHED.md; Mark's OK, 2026-11-08): mradermacher's static Sage-A1.5 Q6_K, the same
# packager and quant as the base Qwen3.6-35B-A3B Q6_K already measured. Pinned to revision fedd56b6; size and sha256 from
# the HF API (LFS oid) in sage_q6_files.txt. Resumable: rerun to continue; verified files are skipped; a mismatch -> .bad.
# Usage: download_sage_q6.sh DEST_DIR    (DEST_DIR/download.log ends "ALL OK" or "FAILED <n>")
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; DEST=${1:?usage: download_sage_q6.sh DEST_DIR}
REPO=mradermacher/Sage-A1.5-GGUF; REV=fedd56b69117f706f48d0ac4ec565e9211d4407d
mkdir -p "$DEST"; LOG="$DEST/download.log"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
bad=0
while read -r p s h; do
  f="$DEST/$p"; [ -e "$f.verified" ] && continue
  free=$(df --output=avail -B1 "$DEST" | tail -1); [ "$free" -gt $((s + 20000000000)) ] || { log "FAILED disk ($free free)"; exit 1; }
  log "start $p ($s bytes)"
  curl -fsSL --retry 30 --retry-delay 15 --retry-all-errors -C - -o "$f" "https://huggingface.co/$REPO/resolve/$REV/$p" \
    || { log "CURL-FAIL $p"; bad=$((bad + 1)); continue; }
  [ "$(stat -c %s "$f")" = "$s" ] || { log "SIZE-MISMATCH $p"; mv "$f" "$f.bad"; bad=$((bad + 1)); continue; }
  [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$h" ] || { log "SHA-MISMATCH $p"; mv "$f" "$f.bad"; bad=$((bad + 1)); continue; }
  echo "$h" > "$f.verified"; log "OK $p"
done < "$HERE/sage_q6_files.txt"
[ "$bad" = 0 ] && log "ALL OK" || log "FAILED $bad"
