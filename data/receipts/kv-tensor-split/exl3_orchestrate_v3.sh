#!/bin/bash
# v3, after v2 misfired: v2 found the registered-stage pid already dead (the killed first orchestrator
# had ALREADY launched the tensor stages), launched a duplicate tensor job that the driver's preflight
# refused, then restored the proxy while the real tensor job (pid 3413262) was still running. v3 waits
# for that job by explicit pid, runs only the Q6K perplexity repair, then restores the proxy.
cd /mnt/TG_2TB/Projects/Apollo || exit 1
LOG=data/receipts/kv-tensor-split/exl3_sm60/orchestrate.log
log () { echo "$(date '+%F %T') $*" >> "$LOG"; }
DM=apollo-proxy-deadman-143720
TPID=3413262
alive () { st=$(timeout 20 ssh -o BatchMode=yes 10.0.0.73 "kill -0 $1 2>/dev/null && echo ALIVE || echo DEAD" 2>/dev/null); [ "$st" != "DEAD" ]; }
log "orchestrator v3 up (pid $$); proxy=$(systemctl --user is-active apollo-wake-proxy); waiting for the running tensor job, pid $TPID"
while alive $TPID; do sleep 30; done
log "tensor job finished"
timeout 30 ssh -o BatchMode=yes 10.0.0.73 'cd ~ && setsid nohup python3 -u exl3_sm60_qual_v2.py PPL-Q6K-repair > ~/exl3_qual/run_repair.out 2>&1 < /dev/null & echo $! > ~/exl3_qual/run_repair.pid'
QPID=$(timeout 20 ssh -o BatchMode=yes 10.0.0.73 'cat ~/exl3_qual/run_repair.pid')
log "Q6K perplexity repair launched, pid $QPID"
while alive $QPID; do sleep 30; done
log "Q6K perplexity repair finished"
systemctl --user start apollo-wake-proxy && log "wake proxy RESTARTED -> $(systemctl --user is-active apollo-wake-proxy)"
systemctl --user stop $DM.timer 2>/dev/null && log "dead-man $DM disarmed"
timeout 120 rsync -a 10.0.0.73:exl3_qual/ data/receipts/kv-tensor-split/exl3_sm60/ && log "results pulled into the repo"
log "=== ORCHESTRATION COMPLETE (v3) ==="
