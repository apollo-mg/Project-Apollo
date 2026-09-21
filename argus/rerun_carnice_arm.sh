#!/usr/bin/env bash
# Carnice-V3 arm, RE-RUN. The 2026-08-26 arm (5/11 clean) is void: it ran against a calendar
# whose events sat on 08-27, so "clear my afternoon" had no target and clean was unearned
# (AFM-25). Same slot as the original -- port 8084, GPUs 0,1 -- so only the DATE differs.
# The driver now refuses to start if the world cannot satisfy the scenario.
set -u
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
H=10.0.0.194

# Stop the stock server by PID (never pkill -f a pattern this shell matches).
ssh $H 'P=$(for p in $(pgrep -x llama-server); do
           [ "$(tr "\0" "\n" < /proc/$p/cmdline | grep -A1 "^--port$" | tail -1)" = "8084" ] && echo $p; done)
        [ -n "$P" ] && { echo "stopping stock server pid $P"; kill $P; sleep 15; }' 

ssh $H "export GGML_CUDA_ALLREDUCE=internal; CUDA_VISIBLE_DEVICES=0,1 numactl --cpunodebind=0 --membind=0 \
  setsid nohup ~/buun-llama-cpp/build_sm60_new/bin/llama-server -m ~/AI/Models/Carnice-V3-Q6_K.gguf \
  -ngl 99 -c 65536 -np 1 -sm tensor -fit off -ctk f16 -ctv f16 -fa on --jinja \
  --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' \
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --presence-penalty 0.0 \
  --host 0.0.0.0 --port 8084 > ~/argus_carnice_8084.log 2>&1 < /dev/null & disown
  for i in \$(seq 1 40); do [ \"\$(curl -s -o /dev/null -w %{http_code} -m 3 http://127.0.0.1:8084/health)\" = '200' ] && { echo READY; break; }; sleep 10; done"

# /props is what you GOT; the command line is only what you asked for.
curl -s -m 10 http://$H:8084/props | $PY -c "
import json,sys; p=json.load(sys.stdin).get('default_generation_settings',{}).get('params',{})
print('  verified samplers: temp',p.get('temperature'),'min_p',p.get('min_p'),'top_p',p.get('top_p'),'presence',p.get('presence_penalty'))"

for i in $(seq 1 12); do
  echo "######## carnice-rerun $i/12  $(date -Iseconds)"
  timeout 4000 $PY driver.py --transport gateway --scenarios runs/effort_probe.json \
      --out runs/carnice_rerun.jsonl --events runs/live_carnice_rerun.jsonl --timeout 1800 2>&1 | tail -4
done
echo "######## carnice-rerun done $(date -Iseconds)"
