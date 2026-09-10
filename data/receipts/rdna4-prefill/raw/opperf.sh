#!/usr/bin/env bash
set -u
S=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
: > $S/opperf.log
for op in GATED_DELTA_NET SSM_CONV SSM_SCAN; do
  for fork in tom buun; do
    d=/mnt/TG_2TB/Projects/Apollo/engines/tq_head/build_rocm/bin
    [ "$fork" = buun ] && d=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin
    echo "### $op / $fork" >> $S/opperf.log
    LD_LIBRARY_PATH="$d" timeout 600 "$d/test-backend-ops" perf -o "$op" -b ROCm0 2>/dev/null \
      | sed 's/\x1b\[[0-9;]*m//g' | grep -E "us/run|GFLOPS|GB/s" | head -6 >> $S/opperf.log
  done
done
echo "######## OPPERF DONE" >> $S/opperf.log
