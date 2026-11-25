#!/bin/bash
# Inkling on .73's two P100s: why does the loader put 21.7 GB on CUDA0? Try the default split (verbose), -ts 1,1, and an
# explicit placement of blocks 12-23 on CUDA1. Load only (llama-cli would generate; the server is enough). Proxy restored.
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/inkling-mini; S=$H/raw/diag_split.log
HOST=mark@10.0.0.73; BIN='~/llama.cpp-33aeb17f/build_sm60/bin'; M=/mnt/models/inkling/Inkling-2-Mini-AD-Q6_K.gguf
rx() { ssh -o BatchMode=yes $HOST "$1"; }
curl -s -m 120 -X POST 127.0.0.1:8099/wake > /dev/null; sleep 5; systemctl --user stop apollo-wake-proxy
rx "setsid nohup sleep 3600 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/apollo-busy.inkling"
P=$(rx 'pgrep -x llama-server'); [ -n "$P" ] && rx "kill $P"
for i in $(seq 60); do u=$(rx "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1"); [ "${u:-99999}" -lt 500 ] && break; sleep 5; done
echo "free check: max used ${u} MiB; $(rx 'nvidia-smi --query-gpu=index,memory.free --format=csv,noheader' | tr '\n' ' ')" >> $S
for cfg in "default|" "ts11|-ts 1,1" "ot|-ot blk\.(1[2-9]|2[0-3])\.=CUDA1"; do
  N=${cfg%%|*}; X=${cfg#*|}
  rx "CUDA_VISIBLE_DEVICES=0,1 GGML_CUDA_ALLREDUCE=internal timeout 240 $BIN/llama-server -m $M -ngl 99 -sm layer -fit off -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0 $X -lv 4 --port 8191 > ~/inkling/diag_$N.log 2>&1 & SP=\$!; ok=0; for i in \$(seq 110); do curl -s -m 2 127.0.0.1:8191/health | grep -q ok && { ok=1; break; }; kill -0 \$SP 2>/dev/null || break; sleep 2; done; kill \$SP 2>/dev/null; wait \$SP 2>/dev/null; echo \"$N healthy=\$ok\"" >> $S 2>&1
  rx "grep -E 'model buffer size|offloaded|CUDA[01].*buffer|failed to allocate' ~/inkling/diag_$N.log | head -8" >> $S 2>&1
  sleep 5
done
scp -q "$HOST:inkling/diag_*.log" $H/raw/ 2>/dev/null
rx "kill \$(cat /tmp/apollo-busy.inkling) 2>/dev/null; rm -f /tmp/apollo-busy.inkling"
systemctl --user start apollo-wake-proxy; echo "DIAG_DONE $(date '+%T')" >> $S
