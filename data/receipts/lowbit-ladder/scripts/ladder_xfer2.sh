#!/usr/bin/env bash
# Transfer the four OUTSTANDING ladder models to .73 and verify each by sha256 ON BOTH ENDS.
# G-IQ2XS is already hash-verified on the node and is deliberately not in the manifest: the
# original script would have re-read 8.77 GB twice to re-confirm a known-good file.
#
# NOTE: the ssh call MUST have -n. Inside a `while read ... done < file` loop ssh
# inherits the manifest as stdin and swallows the remaining lines, so the loop silently
# processes exactly one file and reports DONE. Now a mapfile/for loop as well, so there is
# no shared stdin to consume in the first place.
#
# The gate-model transfer logged a single hash and it turned out to be the SOURCE, so the remote
# copy was never actually verified by that log. Both ends, every file, or it is not a check.
set -uo pipefail
MAN="${1:?manifest required}"
LOG=/tmp/ladder_xfer2.log
: > "$LOG"
mapfile -t FILES < "$MAN"
for f in "${FILES[@]}"; do
  [ -z "$f" ] && continue
  b=$(basename "$f")
  echo "[$(date +%H:%M:%S)] START $b" >> "$LOG"
  rsync -a --partial --inplace "$f" mark@10.0.0.73:/mnt/HDD/ladder/ >> "$LOG" 2>&1
  rc=$?
  src=$(sha256sum "$f" | cut -d' ' -f1)
  dst=$(ssh -n -o BatchMode=yes mark@10.0.0.73 "sha256sum /mnt/HDD/ladder/$b 2>/dev/null | cut -d' ' -f1")
  if [ -n "$dst" ] && [ "$src" = "$dst" ]; then
    echo "[$(date +%H:%M:%S)] OK    $b rc=$rc src=${src:0:16} dst=${dst:0:16}" >> "$LOG"
  else
    echo "[$(date +%H:%M:%S)] FAIL  $b rc=$rc src=${src:0:16} dst=${dst:-NONE}" >> "$LOG"
  fi
  curl -s -m 10 -X POST 127.0.0.1:8099/keepalive > /dev/null 2>&1
done
echo "[$(date +%H:%M:%S)] DONE" >> "$LOG"
