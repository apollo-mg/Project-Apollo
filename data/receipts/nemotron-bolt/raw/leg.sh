#!/bin/sh
# leg.sh LABEL [extra server args...] -> fresh llama-server v0.7.0 on :8091, bench, stop by recorded PID.
LABEL=$1; shift
O=/mnt/HDD/bench/nemotron-bolt-spin-1015; M="/mnt/models/AI_Models/Nemotron 3.5/Bolt-74B-A9B-24GB"
B=/mnt/HDD/llama.cpp-v0.7.0/build_sm60/bin/llama-server
echo "$LABEL start $(date +%T) $(nvidia-smi --query-gpu=index,clocks.sm,memory.used --format=csv,noheader | tr '\n' ' ')" >> $O/state.log
setsid "$B" -m "$M/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB.gguf" -ngl 99 -c 16384 -np 1 -fa on --host 127.0.0.1 --port 8091 "$@" > $O/server_$LABEL.log 2>&1 < /dev/null &
SP=$!; echo $SP > $O/server.pid
python3 -I $O/bench.py $LABEL 8091 $O/$LABEL.jsonl > $O/bench_$LABEL.txt 2>&1
echo "$LABEL bench rc=$? $(date +%T) $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')" >> $O/state.log
kill $SP; tail --pid=$SP -f /dev/null
echo "$LABEL end $(date +%T)" >> $O/state.log
