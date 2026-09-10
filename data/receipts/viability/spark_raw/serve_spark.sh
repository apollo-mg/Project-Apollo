#!/usr/bin/env bash
# Spark-X2.5-4B on gfx1201 via XHToken/llama.cpp 4a3635c32. -c 8192 matches every other
# tier_cal arm so escalation caps identically; the model claims 1M native but that is not
# what is under test here.
set -u
B=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/spark-llama/build_rocm/bin/llama-server
M=/mnt/TG_2TB/AI/Models/spark25/Spark-X2.5-4B-Q4_K_M.gguf
exec $B -m $M -ngl 99 -c 65536 -np 1 -fa on --host 127.0.0.1 --port 8086
