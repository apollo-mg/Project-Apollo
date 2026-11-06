#!/usr/bin/env bash
# After download_ripple.sh: convert the official BF16 weights to Q8_0 with llama.cpp 67107ac34f's converter (our own file,
# no packager in between), hash it, wait for the DeepSeek move to free .194, copy it there and check the hash on .194.
# Runs on the desktop. Log: /mnt/TG_2TB/AI/Models/ripple-65b-gguf/stage.log (last line STAGED <sha256> or FAILED ...).
echo $$ > /tmp/ripple_stage.pid
set -u
ROOT=/mnt/TG_2TB/Projects/Apollo; SRC=/mnt/TG_2TB/AI/Models/ripple-65b; OUTD=/mnt/TG_2TB/AI/Models/ripple-65b-gguf
OUT=$OUTD/Ripple-65B-Preview-Q8_0.gguf; mkdir -p "$OUTD"; LOG=$OUTD/stage.log
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
while [ "$(systemctl --user show ripple-dl -p ActiveState --value 2>/dev/null)" = active ]; do sleep 60; done
tail -1 "$SRC/download.log" | grep -q "ALL OK$" || { log "FAILED: download did not end ALL OK: $(tail -1 "$SRC/download.log")"; exit 1; }
log "converting"
cd /tmp   # never run from the download directory
"$ROOT/venv_cachyos/bin/python3" "$ROOT/engines/llama_cpp_67107ac/convert_hf_to_gguf.py" "$SRC" --outtype q8_0 --outfile "$OUT" \
  > "$OUTD/convert.log" 2>&1 || { log "FAILED: convert exit $? ($(tail -2 "$OUTD/convert.log" | tr '\n' ' '))"; exit 1; }
h=$(sha256sum "$OUT" | cut -d' ' -f1); log "converted: $(stat -c %s "$OUT") bytes sha256 $h"
while [ "$(systemctl --user show ds41-move -p ActiveState --value 2>/dev/null)" = active ]; do sleep 60; done
tail -1 /mnt/HDD/Models/ds41/move.log | grep -q "ALL VERIFIED" || log "note: DeepSeek move did not end ALL VERIFIED ($(tail -1 /mnt/HDD/Models/ds41/move.log)); staging anyway if room"
free=$(ssh 10.0.0.194 'df --output=avail -B1 ~ | tail -1')
[ "$free" -gt $(( $(stat -c %s "$OUT") + 20000000000 )) ] || { log "FAILED: .194 has $free bytes free"; exit 1; }
ssh 10.0.0.194 'mkdir -p ~/AI/Models/ripple'
scp -q "$OUT" 10.0.0.194:AI/Models/ripple/ || { log "FAILED: scp"; exit 1; }
r=$(ssh 10.0.0.194 'sha256sum ~/AI/Models/ripple/Ripple-65B-Preview-Q8_0.gguf' | cut -d' ' -f1)
[ "$r" = "$h" ] && log "STAGED $h" || log "FAILED: hash on .194 $r != $h"
