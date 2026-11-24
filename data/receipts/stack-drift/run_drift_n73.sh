#!/bin/bash
# .73 is the wake-on-demand daily node: pause the wake proxy (Mark's OK for the drift test), stop the daily server, run,
# then start the proxy again (it manages .73 from there).
R=/mnt/TG_2TB/Projects/Apollo; S=$R/data/receipts/stack-drift/raw/state_drift_n73.log
systemctl --user stop apollo-wake-proxy; echo "wake proxy stopped $(date '+%F %T')" >> $S
P=$(ssh -o BatchMode=yes mark@10.0.0.73 'pgrep -x llama-server'); [ -n "$P" ] && ssh -o BatchMode=yes mark@10.0.0.73 "kill $P"; echo "daily server pids stopped: ${P:-none} $(date '+%F %T')" >> $S
bash $R/data/receipts/stack-drift/run_drift.sh n73
systemctl --user start apollo-wake-proxy; echo "wake proxy started $(date '+%F %T')" >> $S
