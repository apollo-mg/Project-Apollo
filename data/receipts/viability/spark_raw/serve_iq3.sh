#!/usr/bin/env bash
# IQ3 glimpse server on the 9070 XT. -c 8192 matches the escalation ceiling of the Q6_K
# reference arms; changing it would make NO-STOP counts incomparable. Port 8085 to avoid
# the wake proxy (8099) and any local sidecar.
set -u
B=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin/llama-server
M=/mnt/TG_2TB/AI/Models/Qwen3.8-27B-AD-IQ3_XXS.gguf
exec $B -m $M -ngl 99 -c 8192 -fa on --host 127.0.0.1 --port 8085
