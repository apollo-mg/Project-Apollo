#!/usr/bin/env bash
# Start the prism batch the moment the stock batch finishes, so both P100s are never idle.
#
# GATED on BATCH_DONE actually appearing. If the stock batch dies instead of completing, the
# prism cells do NOT run: they would contend for VRAM with whatever state that left behind, and
# a panel with a broken stock arm is not worth extending.
#
# The two batches must not overlap. The frozen invocation spans BOTH P100s via `-sm layer`, and
# that is the configuration ref.kld was produced under -- giving each binary its own GPU would
# be faster and would silently change the thing being measured.
set -u
for i in $(seq 1 240); do                 # up to 2 h
  if grep -q "BATCH_DONE" /home/mark/ladder/cells/batch.log 2>/dev/null; then
    echo "$(date -Is) stock batch complete; starting prism batch" >> /home/mark/ladder/chain.log
    bash /home/mark/run_prism_cells.sh
    echo "$(date -Is) prism batch returned" >> /home/mark/ladder/chain.log
    exit 0
  fi
  if ! kill -0 "$(cat /home/mark/ladder/cells.pid 2>/dev/null)" 2>/dev/null; then
    if grep -q "BATCH_DONE" /home/mark/ladder/cells/batch.log 2>/dev/null; then continue; fi
    echo "$(date -Is) stock batch process gone WITHOUT BATCH_DONE -- not starting prism cells" >> /home/mark/ladder/chain.log
    exit 1
  fi
  sleep 30
done
echo "$(date -Is) timed out waiting for the stock batch" >> /home/mark/ladder/chain.log
exit 1
