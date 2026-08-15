#!/usr/bin/env bash
# Wait for both Q6_K files, verify them, then run the draft-head A/B.
set -u
for i in $(seq 1 480); do            # up to 4h of waiting
  grep -q "DOWNLOADS DONE" /home/mark/dl_q6k.log 2>/dev/null && break
  sleep 30
done
grep -q "DOWNLOADS DONE" /home/mark/dl_q6k.log 2>/dev/null || { echo "downloads did not finish"; exit 1; }
grep -q "### FAILED" /home/mark/dl_q6k.log && { echo "a download FAILED, not benchmarking"; exit 1; }
# size sanity: a truncated GGUF loads fine until it doesn't
for f in bartowski unsloth; do
  p=/home/mark/models/$f-Qwen3.8-27B-Q6_K.gguf
  s=$(stat -c%s "$p" 2>/dev/null || echo 0)
  echo "  $f $s bytes"
  [ "$s" -gt 20000000000 ] || { echo "ABORT: $p looks truncated"; exit 1; }
done
sleep 10
exec /home/mark/mtp73/pkg_mtp_ab.sh
