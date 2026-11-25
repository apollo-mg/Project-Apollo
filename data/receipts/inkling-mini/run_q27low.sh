#!/bin/bash
# PREREG_Q27_LOW: Qwen3.8-27B on .73, thinking on, effort low; preflight checks the rendered prompt. Proxy paused and restored.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/inkling-mini; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
S=$H/raw/state_q27low.log; log() { echo "$* $(date '+%F %T')" >> $S; }
HOST=mark@10.0.0.73; IP=10.0.0.73; PORT=8190; BIN='~/llama.cpp-33aeb17f/build_sm60/bin'; M=/mnt/HDD/kld/Qwen3.8-27B-Q8_0.gguf
FLAGS="-ngl 99 -sm layer -fit off -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0"
rx() { ssh -o BatchMode=yes $HOST "$1"; }
curl -s -m 120 -X POST 127.0.0.1:8099/wake > /dev/null; sleep 5
systemctl --user stop apollo-wake-proxy; log "wake proxy stopped"
rx "setsid nohup sleep 21600 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/apollo-busy.q27low"
P=$(rx 'pgrep -x llama-server'); [ -n "$P" ] && rx "kill $P"
for i in $(seq 60); do u=$(rx "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1"); [ "${u:-99999}" -lt 500 ] && break; sleep 5; done
log "VRAM used before load ${u} MiB; binary $(rx "sha256sum $BIN/llama-server | cut -c1-16")"
rx "mkdir -p ~/inkling; CUDA_VISIBLE_DEVICES=0,1 GGML_CUDA_ALLREDUCE=internal setsid nohup $BIN/llama-server -m $M $FLAGS --host 0.0.0.0 --port $PORT > ~/inkling/server_Q27LOW.log 2>&1 < /dev/null & echo \$! > ~/inkling/server.pid"
ok=0; for i in $(seq 1200); do curl -s -m 3 $IP:$PORT/health | grep -q ok && { ok=1; break; }; sleep 2; done; log "server healthy=$ok"
if [ $ok = 1 ]; then
  PF=$($PY - $IP $PORT <<'PY'
import json, sys, urllib.request
ip, port = sys.argv[1], sys.argv[2]
body = {"messages": [{"role": "user", "content": "Q"}], "chat_template_kwargs": {"enable_thinking": True, "reasoning_effort": "low"}}
p = json.load(urllib.request.urlopen(urllib.request.Request(f"http://{ip}:{port}/apply-template", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})))["prompt"]
ok = "Reasoning effort is set to low" in p and not p.rstrip().endswith("</think>")
print(("PASS" if ok else "FAIL") + " tail=" + repr(p[-160:]))
PY
)
  log "preflight $PF"
  if [ "${PF%% *}" = PASS ]; then
    ( cd $QA && $PY run_main.py --url http://$IP:$PORT --arm Q27LOW --thinking --max-tokens 4096 --timeout 900 --usage --skip-slot \
        --template-kwargs '{"reasoning_effort": "low"}' \
        --meta "{\"model\": \"Qwen3.8-27B-Q8_0.gguf (a680f44a)\", \"commit\": \"33aeb17f8\", \"flags\": \"$FLAGS\", \"host\": \".73 2x P100\", \"prereg\": \"PREREG_Q27_LOW.md\"}" > $H/raw/run_Q27LOW.log 2>&1 )
    log "Q27LOW rc=$? rows=$(( $(wc -l < $QA/raw/main_Q27LOW.jsonl) - 1 ))"
  else log "STOP: preflight failed"; fi
fi
rx "kill \$(cat ~/inkling/server.pid) 2>/dev/null"; sleep 5; scp -q "$HOST:inkling/server_Q27LOW.log" $H/raw/
rx "kill \$(cat /tmp/apollo-busy.q27low) 2>/dev/null; rm -f /tmp/apollo-busy.q27low"
systemctl --user start apollo-wake-proxy; log "wake proxy started; Q27LOW_DONE"
