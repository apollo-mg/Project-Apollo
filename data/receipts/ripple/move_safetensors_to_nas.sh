#!/usr/bin/env bash
# Move Ripple-65B-Preview's downloaded BF16 safetensors (130 GB, /mnt/TG_2TB/AI/Models/ripple-65b) to the NAS (Mark's OK,
# 2026-11-08): redundant on the desktop now that the BF16 GGUF is on the NAS and the Q6_K exists; the desktop drive was at
# 27 GB free. rsync removes a source only after its file transferred; every moved shard is then re-hashed on the NAS
# against its .verified (published) sha256. Log: /mnt/HDD/Models/ripple-65b/safetensors/move.log (ALL VERIFIED / MISMATCH n).
echo $$ > /tmp/move_ripple.pid
set -u
SRC=/mnt/TG_2TB/AI/Models/ripple-65b; DST=/mnt/HDD/Models/ripple-65b/safetensors; mkdir -p "$DST"; LOG="$DST/move.log"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
log "moving $(du -sb "$SRC" | cut -f1) bytes"
rsync -a --remove-source-files --partial "$SRC/" "$DST/" >> "$LOG" 2>&1; log "rsync exit $?"
bad=0
for v in "$DST"/*.safetensors.verified; do
  f=${v%.verified}; [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$(cat "$v")" ] && log "verified ${f##*/}" || { log "MISMATCH ${f##*/}"; bad=$((bad + 1)); }
done
[ "$bad" = 0 ] && log "ALL VERIFIED" || log "MISMATCH $bad"
