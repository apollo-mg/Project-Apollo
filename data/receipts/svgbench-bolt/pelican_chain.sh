#!/bin/sh
O=/mnt/HDD/bench/nemotron-bolt-pelican-1015; M="/mnt/models/AI_Models/Nemotron 3.5/Bolt-74B-A9B-24GB"
B=/mnt/HDD/llama.cpp-v0.7.0/build_sm60/bin/llama-server
echo $$ > /tmp/apollo-busy.bolt-pelican; trap "rm -f /tmp/apollo-busy.bolt-pelican" EXIT
echo "start $(date +%T) $(nvidia-smi --query-gpu=index,clocks.sm,memory.used --format=csv,noheader | tr '\n' ' ')" >> $O/state.log
setsid "$B" -m "$M/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB.gguf" -ngl 99 -c 24576 -np 1 -fa on --host 127.0.0.1 --port 8091 > $O/server.log 2>&1 < /dev/null &
SP=$!
python3 -I $O/pelican.py $O 5 > $O/pelican.txt 2>&1
echo "bench rc=$? $(date +%T) $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')" >> $O/state.log
kill $SP; tail --pid=$SP -f /dev/null; echo PELICAN_DONE >> $O/state.log
