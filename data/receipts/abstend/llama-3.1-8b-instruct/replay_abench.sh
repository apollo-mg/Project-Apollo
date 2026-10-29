#!/bin/bash
# Diagnostic server for replay_abench.py: same binary, file and flags as LLAMA8 and L31AB; Clef paused, restored by ExecStopPost.
S=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_upstream_f74e2fa/build_rocm/bin/llama-server
M=/mnt/TG_2TB/models_small/gguf/Meta-Llama-3.1-8B-Instruct-Q8_0.gguf
systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
$BIN -m $M -ngl 99 -c 32768 -np 1 -ctk f16 -ctv f16 --cache-ram 0 --host 127.0.0.1 --port 8197 > $S/replay_server.log 2>&1 < /dev/null & SP=$!
for i in $(seq 1 60); do sleep 3; curl -s -m 3 127.0.0.1:8197/health | grep -q '"ok"' && break; done
python3 -I $S/replay_abench.py $S/replay_result.json > $S/replay_out.txt 2>&1
[ "$(readlink /proc/$SP/exe)" = "$(readlink -f $BIN)" ] && kill $SP && timeout 60 tail --pid=$SP -f /dev/null
echo REPLAY_DONE >> $S/replay_out.txt
