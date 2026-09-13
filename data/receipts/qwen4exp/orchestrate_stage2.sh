#!/bin/bash
# Stage 2 of PREREG_FLASHNEXT_RESIDENCY.md, from the control plane. Launch detached FROM A FOREGROUND CALL.
# Waits for the verified EXL3 download, builds a sha256 manifest, copies the snapshot to .194, waits for the
# post-Stage-1 verifier to finish, then starts the driver with --stage2 on .194. Every check aborts.
set -u
cd /mnt/TG_2TB/Projects/Apollo || exit 1
Q=data/receipts/qwen4exp
LOG=$Q/flashnext_res/orchestrate_stage2.log
SRC=/mnt/TG_2TB/AI/Models/exl3/Qwen3.8-Flash-Next-exl3-3.05bpw_h5_ng5
FLOG=/mnt/TG_2TB/AI/Models/exl3/fetch_flashnext_3.05bpw.log
N=10.0.0.194
DST=AI/Models/exl3/Qwen3.8-Flash-Next-exl3-3.05bpw_h5_ng5
MAN=$Q/flashnext_res/manifest_F-X3.txt
log () { echo "$(date '+%F %T') $*" >> "$LOG"; }
die () { log "ABORT: $*"; exit 1; }
s () { timeout 120 ssh -o BatchMode=yes -o ConnectTimeout=8 "$N" "$@"; }
mkdir -p "$(dirname "$LOG")"
log "stage-2 orchestrator up (pid $$)"

# 1. the download must finish AND verify; a dead fetcher without the marker is a failure, not a wait
for i in $(seq 1 240); do
  grep -q "ALL FILES VERIFIED" "$FLOG" && break
  if ! ps -eo args | grep -q "[h]f_fetch.py turboderp/Qwen3.8-Flash-Next-exl3"; then
    sleep 5; grep -q "ALL FILES VERIFIED" "$FLOG" || die "hf_fetch exited without ALL FILES VERIFIED (last: $(tail -1 "$FLOG"))"
  fi
  sleep 30
done
grep -q "ALL FILES VERIFIED" "$FLOG" || die "download never verified within 2 h"
log "download verified: $(du -sh "$SRC" | cut -f1)"

# 2. manifest: sha256 of every file, relative paths, computed from the verified copy
( cd "$SRC" && find . -type f ! -name '.*' ! -name '*.part' ! -name '*.lock' -printf '%P\n' | sort \
    | xargs -d '\n' -P 8 -n 1 sha256sum ) > "$MAN.tmp" || die "manifest build failed"
sort -k2 "$MAN.tmp" > "$MAN" && rm -f "$MAN.tmp"
[ "$(wc -l < "$MAN")" -ge 5 ] || die "manifest lists only $(wc -l < "$MAN") files"
log "manifest: $(wc -l < "$MAN") files"

# 3. room on .194, then the copy
FREE=$(s "df -BG --output=avail ~ | tail -1 | tr -dc 0-9")
NEED=$(( $(du -s -BG "$SRC" | cut -f1 | tr -dc 0-9) + 5 ))
{ [ -n "$FREE" ] && [ "$FREE" -ge "$NEED" ]; } || die "only ${FREE:-?} GB free on .194, need $NEED"
s "mkdir -p ~/$DST" || die "cannot create $DST on .194"
t0=$(date +%s)
timeout 5400 rsync -a --partial --exclude '.*' --exclude '*.part' "$SRC"/ "$N:$DST"/ || die "rsync failed"
log "copied to .194 in $(( $(date +%s) - t0 )) s (${FREE} GB was free)"
scp -q -o BatchMode=yes "$MAN" "$N:flashnext_res/manifest_F-X3.txt" || die "manifest copy failed"

# 4. the Stage 2 driver, byte-identical to the committed revision
scp -q -o BatchMode=yes "$Q/flashnext_residency.py" "$N:flashnext_res/flashnext_residency.py" || die "driver copy failed"
[ "$(sha256sum "$Q/flashnext_residency.py" | cut -d' ' -f1)" = "$(s 'sha256sum ~/flashnext_res/flashnext_residency.py' | cut -d' ' -f1)" ] \
  || die "staged driver differs from the committed one"
log "driver staged"

# 5. the post-Stage-1 verifier must be done before Stage 2 touches the GPUs
v=""
for i in $(seq 1 120); do
  v=$(s "grep -hE 'VERIFY COMPLETE|ABORT' ~/flashnext_res/verify/verify.log" 2>/dev/null)
  echo "$v" | grep -q "VERIFY COMPLETE" && break
  echo "$v" | grep -q "ABORT" && die "post-Stage-1 verifier aborted: $v"
  sleep 30
done
echo "$v" | grep -q "VERIFY COMPLETE" || die "verifier never completed"
log "verifier complete"

# 6. launch; the driver re-checks every gate (build, hashes, GPUs empty, no contention) and the manifest
s "cd ~/flashnext_res && (setsid nohup python3 -u flashnext_residency.py --stage2 >> driver.out 2>&1 < /dev/null &); sleep 8; tail -2 driver.log" >> "$LOG" 2>&1
log "=== STAGE 2 DRIVER LAUNCHED ==="
