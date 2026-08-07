#!/usr/bin/env bash
# pfetch — parallel HTTP range fetch straight into the destination file.
#
# WHY PARALLEL: HuggingFace rate-limits PER CONNECTION. Measured on this fleet 2026-08-07:
#   1 stream   ~10 MB/s
#   4 streams  ~40 MB/s
#   8 streams  ~100 MB/s   <- saturates a ~800 Mbit line; more streams gain nothing
# The bandwidth was always there; a single curl just never sees it.
#
# WHY NO CONCATENATION: earlier revisions downloaded to N part files and merged them. Two problems,
# both hit for real on the 28.5 GB Qwen base:
#   1. `cat parts/* > out` needs parts AND output on disk simultaneously = 2x filesize. With 30 GB
#      free and a 28.5 GB file that is an ENOSPC after the whole download has already succeeded.
#   2. Even the streaming append-then-delete fix still rewrites every byte a second time, and that
#      merge ran at ~14 MB/s — slower than the download it was serving.
# Each curl now seeks to its own offset in one preallocated file, so bytes are written exactly once
# and peak disk is exactly the filesize. No merge step exists to be slow or to run out of room.
#
# USAGE
#   pfetch.sh <url> <dest> [streams]      # default 8
set -u
URL="${1:?usage: pfetch.sh <url> <dest> [streams]}"
OUT="${2:?usage: pfetch.sh <url> <dest> [streams]}"
N="${3:-8}"

[ -s "$OUT" ] && { echo "SKIP (exists): $OUT"; exit 0; }

SZ=$(curl -sIL "$URL" | awk 'BEGIN{IGNORECASE=1}/^content-length:/{v=$2} END{gsub(/\r/,"",v); print v}')
{ [ -z "$SZ" ] || [ "$SZ" -lt 1000 ]; } && { echo "FATAL: bad content-length '$SZ' from $URL" >&2; exit 1; }

AVAIL=$(df --output=avail -B1 "$(dirname "$OUT")" | tail -1)
if [ "$AVAIL" -lt "$SZ" ]; then
  echo "FATAL: need $SZ bytes, only $AVAIL free at $(dirname "$OUT")" >&2; exit 1
fi

echo "pfetch: $(basename "$OUT")  $SZ bytes  $N streams  (single-write, no merge)"
# Preallocate so every stream can seek without extending the file underneath the others.
fallocate -l "$SZ" "$OUT.tmp" 2>/dev/null || truncate -s "$SZ" "$OUT.tmp" || {
  echo "FATAL: could not preallocate $OUT.tmp" >&2; exit 1; }

CH=$(( (SZ + N - 1) / N ))
rc=0
for i in $(seq 0 $((N-1))); do
  st=$((i*CH)); en=$((st+CH-1)); [ "$en" -ge "$SZ" ] && en=$((SZ-1))
  (
    curl -sL --retry 5 --retry-delay 5 -r "${st}-${en}" "$URL" \
      | dd of="$OUT.tmp" bs=1M seek="$st" oflag=seek_bytes conv=notrunc status=none
  ) &
done
wait || rc=1

FINAL=$(stat -c%s "$OUT.tmp")
if [ "$FINAL" -ne "$SZ" ]; then
  echo "FATAL: got $FINAL bytes, expected $SZ — leaving $OUT.tmp for inspection" >&2; exit 1
fi
# Cheap integrity signal: a torn range write usually leaves a hole of zeros at a chunk boundary.
for i in $(seq 1 $((N-1))); do
  off=$((i*CH))
  b=$(dd if="$OUT.tmp" bs=1 skip=$((off-8)) count=16 status=none 2>/dev/null | tr -d '\0' | wc -c)
  [ "$b" -eq 0 ] && echo "WARN: 16 zero bytes across boundary $i (offset $off) — verify this file" >&2
done
head -c 4 "$OUT.tmp" | grep -q GGUF || echo "NOTE: no GGUF magic (fine if this is not a GGUF)" >&2

mv "$OUT.tmp" "$OUT"
echo "pfetch: OK $FINAL bytes -> $OUT"
exit $rc
