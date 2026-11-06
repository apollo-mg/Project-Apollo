#!/usr/bin/env bash
# Move the two DeepSeek-V4.1 builds from .194 (~/AI/Models/ds41, 465 GB) to the NAS (/mnt/HDD/Models/ds41 on the desktop;
# .194 does not mount the NAS), Mark's OK 2026-11-05, to free .194 for Ripple. Runs on the desktop after the Ripple
# download (one NIC). rsync checksums each file in transit and removes a source only after its file transferred. The
# Engram-as-shard-6 symlink is not moved (CIFS); recreate it with `ln -s DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf
# DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00006-of-00006.gguf` in gsq/. Afterwards every moved .gguf is re-hashed on the
# NAS against its .verified (published) sha256. Log: /mnt/HDD/Models/ds41/move.log (last line ALL VERIFIED or MISMATCH n).
echo $$ > /tmp/move_ds41.pid
set -u
DST=/mnt/HDD/Models/ds41; mkdir -p "$DST"; LOG="$DST/move.log"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
while [ "$(systemctl --user show ripple-dl -p ActiveState --value 2>/dev/null)" = active ]; do sleep 60; done
log "ripple download done; moving"
rsync -a --no-links --remove-source-files --partial --info=stats1 10.0.0.194:AI/Models/ds41/ "$DST/" >> "$LOG" 2>&1
log "rsync exit $?"
bad=0
for v in "$DST"/*/*.gguf.verified; do
  f=${v%.verified}; want=$(cat "$v")
  got=$(sha256sum "$f" | cut -d' ' -f1)
  [ "$got" = "$want" ] && log "verified ${f#$DST/}" || { log "MISMATCH ${f#$DST/}: $got"; bad=$((bad + 1)); }
done
[ "$bad" = 0 ] && log "ALL VERIFIED" || log "MISMATCH $bad"
