#!/bin/sh
# usage: numa_sampler.sh PID OUTFILE -- every 0.5 s, one line: the CPU ids of PID's running (R) threads
pid=$1; out=$2; : > "$out"
while kill -0 "$pid" 2>/dev/null; do
  ps -L -o psr=,stat= -p "$pid" | awk '$2 ~ /R/ {printf "%s ", $1} END {print ""}' >> "$out"
  sleep 0.5
done
