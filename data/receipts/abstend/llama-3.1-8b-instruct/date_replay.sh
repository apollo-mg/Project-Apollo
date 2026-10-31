#!/bin/bash
# PREREG_DRIFT_CAUSE.md Addendum 1: same binary, file and flags as LLAMA8 and L31AB. Clef paused; ExecStopPost restores it.
# Launch: systemd-run --user --unit=date-replay --collect -p ExecStopPost="/usr/bin/systemctl --user start apollo-clef.service apollo-clef-monitor.service" bash <this file>
set -u
R=/mnt/TG_2TB/Projects/Apollo; D=$R/data/receipts/abstend/llama-3.1-8b-instruct
BIN=$R/engines/llama_cpp_upstream_f74e2fa/build_rocm/bin/llama-server
M=/mnt/TG_2TB/models_small/gguf/Meta-Llama-3.1-8B-Instruct-Q8_0.gguf
systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
$BIN -m $M -ngl 99 -c 32768 -np 1 -ctk f16 -ctv f16 --cache-ram 0 --host 127.0.0.1 --port 8197 > $R/data/receipts/abstentionbench/raw/date_replay_server.log 2>&1 < /dev/null & SP=$!
for i in $(seq 1 60); do sleep 3; curl -s -m 3 127.0.0.1:8197/health | grep -q '"ok"' && break; done
python3 -I $D/date_replay.py $D/date_replay.json > $D/date_replay.txt 2>&1
[ "$(readlink /proc/$SP/exe)" = "$(readlink -f $BIN)" ] && kill $SP && timeout 60 tail --pid=$SP -f /dev/null
echo DONE >> $D/date_replay.txt
