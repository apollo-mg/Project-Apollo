#!/usr/bin/env bash
# Stage 2 retry (Amendment 4): once the Stage 3 launcher finishes, rerun the F-X3 arm unchanged. Its first attempt
# died on ENOSPC while buun's safetensors loader prepared a streamed tensor in the model directory. Runs ON .194.
set -u
R=~/flashnext_res; L=$R/stage2_retry.log
say () { echo "$(date '+%F %T') $*" >> "$L"; }
busy () { ps -eo args | grep -q "[f]lashnext_residency.py" || pgrep -x llama-server >/dev/null; }
say "stage-2 retry launcher up (pid $$), waiting for the Stage 3 launcher to finish"
for i in $(seq 1 360); do
  grep -qE "STAGE 3 LAUNCHER COMPLETE|gave up|ABORT" "$R/stage3_launcher.log" 2>/dev/null && break
  sleep 30
done
grep -qE "STAGE 3 LAUNCHER COMPLETE|gave up|ABORT" "$R/stage3_launcher.log" || { say "gave up: the Stage 3 launcher never finished"; exit 1; }
for i in $(seq 1 60); do busy || break; sleep 10; done
busy && { say "ABORT: a driver or server is still running"; exit 1; }
FREE=$(df -BG --output=avail ~ | tail -1 | tr -dc 0-9)
[ "${FREE:-0}" -ge 45 ] || { say "ABORT: only ${FREE:-?} GB free; the prepared n-gram table needs ~33 GB plus margin"; exit 1; }
say "free space ${FREE} GB -- rerunning Stage 2"
sleep 20
cd "$R" && python3 -u flashnext_residency.py --stage2 >> "$R/driver.out" 2>&1
say "stage 2 retry driver exited rc=$?"
say "=== STAGE 2 RETRY COMPLETE ==="
