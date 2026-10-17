#!/bin/sh
# Run the 5 pelican reps against the already-loaded Beam server, then stop it by its recorded, verified PID.
O=$HOME/bench/beam-pelican-1017
echo "bench start $(date +%T) $(nvidia-smi --query-gpu=index,clocks.sm,memory.used --format=csv,noheader | tr '\n' ' ')" >> $O/state.log
python3 -I $O/pelican.py $O 5 > $O/pelican.txt 2>&1
echo "bench rc=$? $(date +%T) $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')" >> $O/state.log
p=$(cat $O/server.pid); [ "$(readlink /proc/$p/exe)" = $HOME/llama.cpp-beam/build_sm60/bin/llama-server ] && kill $p && tail --pid=$p -f /dev/null
echo PELICAN_DONE >> $O/state.log
