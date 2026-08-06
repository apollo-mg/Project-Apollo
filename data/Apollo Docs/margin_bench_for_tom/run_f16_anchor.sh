#!/bin/bash


echo "Killing existing servers..."
ssh mark@10.0.0.194 "pkill -f llama-server || true"
sleep 5

echo "Starting Tom f16/f16..."
ssh mark@10.0.0.194 "export TURBO_AUTO_ASYMMETRIC=0 && cd /home/mark/llama-cpp-turboquant/build/bin && nohup ./llama-server -m '/home/mark/AI/Models/Qwen 3.6/27B/Qwopus/Qwopus/Coder/Qwopus3.6-27B-Coder-heretic-Q6_K.gguf' -c 8192 -ctk f16 -ctv f16 --host 0.0.0.0 --port 8080 > /home/mark/tom_f16_server.log 2>&1 &"
sleep 45

echo "Running probe_router for Tom f16..."
cd "/mnt/TG_2TB/Projects/Apollo/data/Apollo Docs/margin_bench_for_tom/router_probe"
python3 probe_router.py --base-url http://10.0.0.194:8080/v1 --model local --data cases/rd_8192_c2.jsonl --out lp_tom_f16.jsonl

echo "Killing Tom f16..."
ssh mark@10.0.0.194 "pkill -f llama-server || true"
sleep 5

echo "Starting Buun f16/f16..."
ssh mark@10.0.0.194 "unset TURBO_AUTO_ASYMMETRIC && cd /home/mark/buun_tree/build/bin && nohup ./llama-server -m '/home/mark/AI/Models/Qwen 3.6/27B/Qwopus/Qwopus/Coder/Qwopus3.6-27B-Coder-heretic-Q6_K.gguf' -c 8192 -ctk f16 -ctv f16 --host 0.0.0.0 --port 8081 > /home/mark/buun_f16_server.log 2>&1 &"
sleep 45

echo "Running probe_router for Buun f16..."
python3 probe_router.py --base-url http://10.0.0.194:8081/v1 --model local --data cases/rd_8192_c2.jsonl --out lp_buun_tcq_f16.jsonl

echo "Killing Buun f16..."
ssh mark@10.0.0.194 "pkill -f llama-server || true"

echo "Running paired_margins on f16 results..."
cd "/mnt/TG_2TB/Projects/Apollo/data/Apollo Docs/margin_bench_for_tom"
python3 paired_margins.py router_probe/lp_tom_f16.jsonl router_probe/lp_buun_tcq_f16.jsonl > f16_paired_results.txt
echo "f16 anchor completed!"
