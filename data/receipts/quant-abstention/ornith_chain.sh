#!/bin/bash
# PREREG_ORNITH chain, run from the desktop against .194:8190: fresh server (all layers on GPU; the Beam spill procedure
# only if it does not load), smoke gate, the instrument's default thinking-off path (render check and R-slot on), M1,
# analysis, then the server is stopped AND waited for, and .194 powered off.
set -u
R=/mnt/TG_2TB/Projects/Apollo; PY=$R/venv_cachyos/bin/python3; Q=$R/data/receipts/quant-abstention; H=http://10.0.0.194:8190
LOG=$Q/raw/ornith_state.log
META='{"model": "unsloth/Ornith-1.5-122B-GGUF UD-Q3_K_XL (3 shards, 59761254545 B, sha256 per shard verified)", "build": "llama.cpp c7fc509 (2026-10-21) build_sm60 gcc-13", "placement": "-ngl 99 -sm layer -c 8192 -ctk f16 -ctv f16 -np 1 -fit off (all layers on GPU unless the state log says otherwise)", "host": ".194 4x P100 150 W", "prereg": "PREREG_ORNITH.md"}'
log () { echo "$(date '+%F %T') $*" >> $LOG; }
log "chain start"
ssh mark@10.0.0.194 'nohup ~/bench/hymem-1019/serve_ornith.sh > /dev/null 2>&1 < /dev/null & echo $! > ~/bench/hymem-1019/server.pid'
ok=0; for i in $(seq 1 120); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && { ok=1; break; }; ssh mark@10.0.0.194 'kill -0 $(cat ~/bench/hymem-1019/server.pid) 2>/dev/null' || break; done
[ $ok = 1 ] || { log "ABORT: server did not come up (see server_ORN.log on .194)"; exit 1; }
log "server up: $(ssh mark@10.0.0.194 'nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr "\n" " "')"
if curl -s -m 600 $H/v1/chat/completions -H 'Content-Type: application/json' \
   -d '{"messages":[{"role":"user","content":"What is 17*19? Answer briefly."}],"temperature":0,"max_tokens":256,"cache_prompt":false,"chat_template_kwargs":{"enable_thinking":false}}' \
   | python3 -c "import sys,json; d=json.load(sys.stdin); m=d['choices'][0]['message']; c=len(m.get('content') or ''); r=len(m.get('reasoning_content') or ''); print('smoke content',c,'reasoning',r, repr((m.get('content') or '')[:60])); sys.exit(0 if c>0 and r==0 else 1)" >> $LOG 2>&1; then
  log "ORN smoke OK"
  cd $Q; $PY -s run_main.py --url $H --arm ORN --usage --max-tokens 1024 --timeout 600 --meta "$META" >> $Q/raw/run_ORN.log 2>&1
  log "ORN rc=$? rows=$(( $(wc -l < raw/main_ORN.jsonl) - 1 ))"
  cd $Q; $PY -s analyze_ornith.py >> $LOG 2>&1; log "analysis rc=$?"
else
  log "ORN SMOKE GATE FAILED: arm not run"
fi
ssh mark@10.0.0.194 'P=$(cat ~/bench/hymem-1019/server.pid); [ "$(readlink /proc/$P/exe)" = "$HOME/llama.cpp-flint/build_sm60/bin/llama-server" ] && kill $P && timeout 60 tail --pid=$P -f /dev/null'
timeout 120 $R/tools/s194.sh off >> $LOG 2>&1
log "DONE"
