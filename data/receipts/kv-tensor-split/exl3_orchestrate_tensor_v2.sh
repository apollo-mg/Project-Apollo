#!/bin/bash
# Replaces exl3_orchestrate_tensor.sh (killed by PID so its stage list could change; a running bash
# script must not be edited in place). Adds Amendment 2's Q6K perplexity repair after the tensor
# stages, then restores the proxy. Launched detached from a foreground call: no harness ancestor.
cd /mnt/TG_2TB/Projects/Apollo || exit 1
LOG=data/receipts/kv-tensor-split/exl3_sm60/orchestrate.log
log () { echo "$(date '+%F %T') $*" >> "$LOG"; }
DM=apollo-proxy-deadman-141449
RPID=3123726
alive () { st=$(timeout 20 ssh -o BatchMode=yes 10.0.0.73 "kill -0 $1 2>/dev/null && echo ALIVE || echo DEAD" 2>/dev/null); [ "$st" != "DEAD" ]; }
log "orchestrator v2 up (pid $$); proxy=$(systemctl --user is-active apollo-wake-proxy); waiting for registered stages, pid $RPID"
while alive $RPID; do sleep 30; done
log "registered stages finished"
timeout 30 ssh -o BatchMode=yes 10.0.0.73 'cd ~ && setsid nohup bash -c "for s in X-27-tensor Q6K-tensor PPL-Q6K-repair; do python3 -u exl3_sm60_qual_v2.py \$s; done" > ~/exl3_qual/run_tensor.out 2>&1 < /dev/null & echo $! > ~/exl3_qual/run_tensor.pid'
TPID=$(timeout 20 ssh -o BatchMode=yes 10.0.0.73 'cat ~/exl3_qual/run_tensor.pid')
log "tensor stages + Q6K perplexity repair launched, pid $TPID"
while alive $TPID; do sleep 30; done
log "tensor stages + repair finished"
systemctl --user start apollo-wake-proxy && log "wake proxy RESTARTED -> $(systemctl --user is-active apollo-wake-proxy)"
systemctl --user stop $DM.timer 2>/dev/null && log "dead-man $DM disarmed"
timeout 120 rsync -a 10.0.0.73:exl3_qual/ data/receipts/kv-tensor-split/exl3_sm60/ && log "results pulled into the repo"
log "=== ORCHESTRATION COMPLETE ==="
