#!/usr/bin/env bash
# END-TO-END: a request arrives for a SLEEPING machine and comes back with a completion.
# Everything before this tested pieces -- suspend/wake on the node, single-flight on a fake
# unreachable target. Nothing has ever exercised the whole path.
set -u
A=/mnt/TG_2TB/Projects/Apollo
PY=$A/venv_cachyos/bin/python3
# -fit off: P100s crash with row-splitting (CLAUDE.md). Small ctx keeps the load fast.
START="setsid nohup /home/mark/buun-llama-cpp/build_sm60_head/bin/llama-server \
-m '/mnt/models/AI_Models/Qwen 3.6/Qwen3.6-27B-Q6_K-MTP.gguf' \
-ngl 99 -c 8192 -np 1 -fit off -fa on --jinja --host 0.0.0.0 --port 8080 \
> /home/mark/wake_proxy_server.log 2>&1 < /dev/null & disown"

echo "=== starting proxy (idle-suspend disabled during the test) ==="
WP_NODE=10.0.0.73 WP_MAC=e0:d5:5e:b5:9e:b3 WP_BCAST=10.0.0.255 WP_PORT=8099 \
WP_LLAMA_PORT=8080 WP_IDLE=99999 WP_SUSPEND=0 WP_WAKE_TIMEOUT=180 WP_LOAD_TIMEOUT=600 \
WP_START_CMD="$START" WP_LOG=$A/run/wake_proxy.log \
setsid nohup $PY $A/modules/wake_proxy.py > /tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/e2e_proxy.log 2>&1 < /dev/null &
P=$!; disown; sleep 6
echo "  proxy pid $P; owns 8099: $(ss -ltnp 2>/dev/null | grep -c ':8099')"

echo "=== put .73 to sleep (nothing loaded, so no VRAM spill) ==="
ssh -n 10.0.0.73 'pkill -x llama-server 2>/dev/null; sleep 3; sudo -n systemd-run --on-active=2 --timer-property=AccuracySec=100ms systemctl suspend' >/dev/null 2>&1
for i in $(seq 1 60); do ping -c1 -W1 10.0.0.73 >/dev/null 2>&1 || { echo "  asleep after ${i}s"; break; }; sleep 1; done
ping -c1 -W1 10.0.0.73 >/dev/null 2>&1 && { echo "  FAIL: did not sleep"; kill $P; exit 1; }
sleep 15

echo "=== ONE request to a sleeping machine ==="
T0=$(date +%s)
curl -s -m 900 -X POST http://127.0.0.1:8099/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen","messages":[{"role":"user","content":"Reply with exactly: awake"}],"max_tokens":24,"temperature":0.1}' \
  -o /tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/e2e_resp.json \
  -w "  HTTP %{http_code} — total %{time_total}s\n"
T1=$(date +%s)
echo "  cold-start wall clock: $((T1-T0))s"
echo "=== response ==="
$PY -c "
import json
d=json.load(open('/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/e2e_resp.json'))
m=(d.get('choices') or [{}])[0].get('message',{})
print('  content:', repr((m.get('content') or m.get('reasoning_content') or '')[:120]))
print('  usage:', d.get('usage'))
" 2>&1 | head -4
echo "=== second request (already warm) ==="
curl -s -m 120 -o /dev/null -X POST http://127.0.0.1:8099/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen","messages":[{"role":"user","content":"say hi"}],"max_tokens":16}' \
  -w "  HTTP %{http_code} — total %{time_total}s\n"
echo "=== proxy status ==="; curl -s -m 10 http://127.0.0.1:8099/status
echo; kill $P 2>/dev/null; echo "  proxy stopped"
