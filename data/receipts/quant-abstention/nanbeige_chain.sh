#!/bin/bash
# PREREG_NANBEIGE.md: N33OFF (thinking off, greedy) and N33THK (thinking on, the card's T 0.6 / top_p 0.95) on .194. Waits
# for the verified download and for the Sage Addendum-1 chain (sage-t1-chain unit) to finish and power .194 off.
set -u
R=/mnt/TG_2TB/Projects/Apollo; PY=$R/venv_cachyos/bin/python3; Q=$R/data/receipts/quant-abstention; H=http://10.0.0.194:8190
LOG=$Q/raw/nanbeige_state.log; S194=mark@10.0.0.194; D=/mnt/HDD/Models/Nanbeige4.3-33B; F=Nanbeige_Nanbeige4.3-33B-Q8_0.gguf
SHA=8523452a975fa67d84a926c9a1bbdbb32b78b2a516dbf14d9360271fc53cd7f1; SAMP='{"temperature": 0.6, "top_p": 0.95}'
log () { echo "$(date '+%F %T') $*" >> $LOG; }
log "waiting for the download and sage-t1-chain"
until [ -f $D/Q8_0.got ] || ! systemctl --user is-active -q dl-nanbeige; do sleep 60; done
[ "$(cut -d' ' -f1 $D/Q8_0.got 2>/dev/null)" = $SHA ] || { log "ABORT: download sha256 mismatch or missing"; exit 1; }
log "download verified"
while systemctl --user is-active -q sage-t1-chain; do sleep 60; done
log "sage-t1-chain finished"; sleep 120
timeout 300 $R/tools/s194.sh on >> $LOG 2>&1
for i in $(seq 1 60); do ssh -o ConnectTimeout=5 -o BatchMode=yes $S194 true 2>/dev/null && break; sleep 10; done
rsync -a $D/$F $S194:/dev/shm/ && got=$(ssh $S194 "sha256sum /dev/shm/$F" | cut -d' ' -f1)
[ "${got:-}" = $SHA ] || { log "ABORT: staged sha256 mismatch (${got:-none})"; timeout 120 $R/tools/s194.sh off >> $LOG 2>&1; exit 1; }
log "staged, sha256 ok; clocks $(ssh $S194 'nvidia-smi --query-gpu=clocks.applications.graphics,power.limit --format=csv,noheader | tr "\n" " "')"
ssh $S194 "nohup ~/bench/sage/serve_sage.sh /dev/shm/$F > ~/bench/sage/server_N33.log 2>&1 < /dev/null & echo \$! > ~/bench/sage/server.pid"
ok=0; for i in $(seq 1 120); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && { ok=1; break; }; done
[ $ok = 1 ] || { log "ABORT: server did not come up"; timeout 120 $R/tools/s194.sh off >> $LOG 2>&1; exit 1; }
log "server up: $(ssh $S194 'nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr "\n" " "')"
smoke () { curl -s -m 1800 $H/v1/chat/completions -H 'Content-Type: application/json' -d "{\"messages\":[{\"role\":\"user\",\"content\":\"What is 17*19? Answer briefly.\"}],\"max_tokens\":4096,\"cache_prompt\":false,\"chat_template_kwargs\":{\"enable_thinking\":$1}$2}" \
  | python3 -c "import sys,json; m=json.load(sys.stdin)['choices'][0]['message']; c=m.get('content') or ''; r=m.get('reasoning_content') or ''; print('content',repr(c[:80]),'reasoning',len(r)); sys.exit(0 if '323' in c and ('$1'=='true' or not r) else 1)"; }
META='{"model": "bartowski Nanbeige_Nanbeige4.3-33B-Q8_0.gguf (sha256 8523452a..., rev 9beb6842)", "build": "llama.cpp c7fc509 build_sm60 gcc-13", "placement": "-ngl 99 -sm layer -c 16384 -ctk f16 -ctv f16 -np 1 -fit off, /dev/shm"}'
cd $Q
if r=$(smoke false ',"temperature":0'); then log "N33OFF smoke OK: $r"
  $PY -s run_main.py --url $H --arm N33OFF --usage --max-tokens 1024 --timeout 600 --meta "$META" >> raw/run_N33OFF.log 2>&1
  log "N33OFF rc=$? rows=$(( $(wc -l < raw/main_N33OFF.jsonl) - 1 ))"; else log "N33OFF SMOKE FAILED: $r"; fi
if r=$(smoke true ',"temperature":0.6,"top_p":0.95,"seed":1'); then log "N33THK smoke OK: $r"
  $PY -s run_main.py --url $H --arm N33THK --usage --thinking --sampling "$SAMP" --max-tokens 8192 --timeout 1800 --meta "$META" >> raw/run_N33THK.log 2>&1
  log "N33THK rc=$? rows=$(( $(wc -l < raw/main_N33THK.jsonl) - 1 ))"; else log "N33THK SMOKE FAILED: $r"; fi
[ -f raw/main_N33OFF.jsonl ] && [ -f raw/main_N33THK.jsonl ] && { $PY -s analyze_nanbeige.py >> $LOG 2>&1; log "analysis rc=$?"; }
ssh $S194 "P=\$(cat ~/bench/sage/server.pid); [ \"\$(readlink /proc/\$P/exe)\" = \"\$HOME/llama.cpp-flint/build_sm60/bin/llama-server\" ] && kill \$P && timeout 60 tail --pid=\$P -f /dev/null; rm -f /dev/shm/$F"
timeout 120 $R/tools/s194.sh off >> $LOG 2>&1
log "DONE"
