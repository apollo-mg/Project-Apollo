#!/bin/bash
# PREREG_NANBEIGE.md stop rule: N33THK interrupted at 180/240 when the desktop session logged out (2026-10-26 03:59,
# which stopped every user unit incl. nanbeige-chain). Resume on a FRESH server: stop the old one (verified pid),
# serve again, smoke, resume (run_main.py skips written ids), analyse, clean up, power .194 off.
set -u
R=/mnt/TG_2TB/Projects/Apollo; PY=$R/venv_cachyos/bin/python3; Q=$R/data/receipts/quant-abstention; H=http://10.0.0.194:8190
LOG=$Q/raw/nanbeige_state.log; S194=mark@10.0.0.194; F=Nanbeige_Nanbeige4.3-33B-Q8_0.gguf; SAMP='{"temperature": 0.6, "top_p": 0.95}'
log () { echo "$(date '+%F %T') $*" >> $LOG; }
log "RESUME 1: N33THK at $(( $(wc -l < $Q/raw/main_N33THK.jsonl) - 1 ))/240 (desktop session logout 03:59 stopped the chain)"
ssh $S194 'P=$(cat ~/bench/sage/server.pid); [ "$(readlink /proc/$P/exe)" = "$HOME/llama.cpp-flint/build_sm60/bin/llama-server" ] && kill $P && timeout 60 tail --pid=$P -f /dev/null; true'
sleep 3; curl -s -m 3 $H/health | grep -q '"ok"' && { log "ABORT: an old server still answers on 8190"; exit 1; }
ssh $S194 "nohup ~/bench/sage/serve_sage.sh /dev/shm/$F > ~/bench/sage/server_N33_resume.log 2>&1 < /dev/null & echo \$! > ~/bench/sage/server.pid"
ok=0; for i in $(seq 1 120); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && { ok=1; break; }; done
[ $ok = 1 ] || { log "ABORT: fresh server did not come up"; exit 1; }
log "fresh server up pid $(ssh $S194 'cat ~/bench/sage/server.pid'): $(curl -s $H/props | python3 -c 'import sys,json; print(json.load(sys.stdin)["model_path"])')"
META='{"model": "bartowski Nanbeige_Nanbeige4.3-33B-Q8_0.gguf (sha256 8523452a..., rev 9beb6842)", "build": "llama.cpp c7fc509 build_sm60 gcc-13", "placement": "-ngl 99 -sm layer -c 16384 -ctk f16 -ctv f16 -np 1 -fit off, /dev/shm", "resumed": "2026-10-26 fresh server"}'
cd $Q
r=$(curl -s -m 1800 $H/v1/chat/completions -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"What is 17*19? Answer briefly."}],"max_tokens":4096,"cache_prompt":false,"temperature":0.6,"top_p":0.95,"seed":1,"chat_template_kwargs":{"enable_thinking":true}}' | python3 -c "import sys,json; m=json.load(sys.stdin)['choices'][0]['message']; print(repr((m.get('content') or '')[:60]))")
log "smoke: $r"
$PY -s run_main.py --url $H --arm N33THK --usage --thinking --sampling "$SAMP" --max-tokens 8192 --timeout 1800 --meta "$META" >> raw/run_N33THK.log 2>&1
log "N33THK rc=$? rows=$(( $(wc -l < raw/main_N33THK.jsonl) - 1 ))"
$PY -s analyze_nanbeige.py >> $LOG 2>&1; log "analysis rc=$?"
ssh $S194 "P=\$(cat ~/bench/sage/server.pid); [ \"\$(readlink /proc/\$P/exe)\" = \"\$HOME/llama.cpp-flint/build_sm60/bin/llama-server\" ] && kill \$P && timeout 60 tail --pid=\$P -f /dev/null; rm -f /dev/shm/$F"
timeout 120 $R/tools/s194.sh off >> $LOG 2>&1
log "DONE"
