#!/usr/bin/env bash
# Run the split x MTP ladder after the packager A/B finishes (or fails).
set -u
for i in $(seq 1 600); do            # up to 5h
  grep -qE "PKG MTP AB DONE|ABORT:" /home/mark/mtp73/pkg_ab.log 2>/dev/null && break
  sleep 30
done
if grep -q "ABORT:" /home/mark/mtp73/pkg_ab.log 2>/dev/null; then
  echo "packager A/B aborted; running split x MTP anyway (independent of it)"
fi
sleep 15
pgrep -x llama-server >/dev/null && { pkill -x llama-server; sleep 8; }
exec /home/mark/mtp73/split_mtp_2x3.sh
