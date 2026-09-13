#!/usr/bin/env bash
# Stage 3b (Amendment 5): the corrected auto-fit arm, run once the Stage 2 retry has finished either way. ON .194.
set -u
R=~/flashnext_res; L=$R/stage3b_launcher.log
say () { echo "$(date '+%F %T') $*" >> "$L"; }
busy () { ps -eo args | grep -q "[f]lashnext_residency.py" || pgrep -x llama-server >/dev/null; }
say "stage-3b launcher up (pid $$), waiting for the Stage 2 retry to finish"
for i in $(seq 1 480); do
  grep -qE "STAGE 2 RETRY COMPLETE|gave up|ABORT" "$R/stage2_retry.log" 2>/dev/null && break
  sleep 30
done
grep -qE "STAGE 2 RETRY COMPLETE|gave up|ABORT" "$R/stage2_retry.log" || { say "gave up: the Stage 2 retry never finished"; exit 1; }
for i in $(seq 1 60); do busy || break; sleep 10; done
busy && { say "ABORT: a driver or server is still running"; exit 1; }
sleep 20
cd "$R" && python3 -u flashnext_residency.py --stage3b >> "$R/driver.out" 2>&1
say "stage 3b driver exited rc=$?"
say "=== STAGE 3B LAUNCHER COMPLETE ==="
