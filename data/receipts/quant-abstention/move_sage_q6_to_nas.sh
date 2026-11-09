#!/usr/bin/env bash
# Move the Sage-A1.5 Q6_K used by PREREG_SAGE_MATCHED.md (29 GB, /mnt/TG_2TB/AI/Models/sage-a15-q6) to the NAS (Mark's
# OK, 2026-11-09): the run is done and the desktop drive was at 121 GB free. rsync removes a source only after its file
# transferred; the moved GGUF is then re-hashed on the NAS against its .verified (HF LFS) sha256.
# Log: /mnt/HDD/Models/sage-a15-q6/move.log (ALL VERIFIED / MISMATCH n).
set -u
SRC=/mnt/TG_2TB/AI/Models/sage-a15-q6; DST=/mnt/HDD/Models/sage-a15-q6; mkdir -p "$DST"; LOG="$DST/move.log"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
log "moving $(du -sb "$SRC" | cut -f1) bytes"
rsync -a --remove-source-files --partial "$SRC/" "$DST/" >> "$LOG" 2>&1; log "rsync exit $?"
bad=0
for v in "$DST"/*.gguf.verified; do
  f=${v%.verified}; [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$(cat "$v")" ] && log "verified ${f##*/}" || { log "MISMATCH ${f##*/}"; bad=$((bad + 1)); }
done
[ "$bad" = 0 ] && log "ALL VERIFIED" || log "MISMATCH $bad"
