#!/bin/bash
# PREREG_FLINT chain, run from the desktop (client) against .194:8190. FLNT on the running --reasoning-budget 0 server,
# then a fresh server without a budget for FLTK, smoke gates before each arm, analysis, then .194 is stopped and
# powered off (Mark: keep it off when idle). `touch raw/FLINT_STOP` skips FLTK.
set -u
R=/mnt/TG_2TB/Projects/Apollo; PY=$R/venv_cachyos/bin/python3; Q=$R/data/receipts/quant-abstention; H=http://10.0.0.194:8190
LOG=$Q/raw/flint_state.log
META='{"model": "unsloth/flint-GGUF flint-Q8_0.gguf (42301076928 B, sha256 5df42b56859c7b5142228005d7d63c327ec9e34c99c72548016d805309a0d284)", "build": "llama.cpp c7fc509 (2026-10-21) build_sm60 gcc-13", "placement": "-ngl 99 -sm layer -c 32768 -ctk f16 -ctv f16 -np 1 -fit off", "host": ".194 4x P100 150 W", "prereg": "PREREG_FLINT.md"}'
log () { echo "$(date '+%F %T') $*" >> $LOG; }
smoke () {   # $1 = want_reasoning (0|1)
  curl -s -m 600 $H/v1/chat/completions -H 'Content-Type: application/json' \
    -d '{"messages":[{"role":"user","content":"What is 17*19? Answer briefly."}],"temperature":0,"max_tokens":4096,"cache_prompt":false}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); m=d['choices'][0]['message']; c=len(m.get('content') or ''); r=len(m.get('reasoning_content') or ''); print('content',c,'reasoning',r); sys.exit(0 if c>0 and ((r>0)==bool($1)) else 1)"
}
serve () {   # $1 = extra server flags
  ssh mark@10.0.0.194 "P=\$(cat ~/bench/hymem-1019/server.pid); [ \"\$(readlink /proc/\$P/exe)\" = \"\$HOME/llama.cpp-flint/build_sm60/bin/llama-server\" ] && kill \$P; sleep 6; sed -i 's|  .*--host 0.0.0.0 --port 8190|  $1 --host 0.0.0.0 --port 8190|' ~/bench/hymem-1019/serve_flint.sh; nohup ~/bench/hymem-1019/serve_flint.sh /dev/shm/flint/flint-Q8_0.gguf FL_$2 > /dev/null 2>&1 < /dev/null & echo \$! > ~/bench/hymem-1019/server.pid"
  for i in $(seq 1 60); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && return 0; done; return 1
}
run_arm () {  # $1 arm, $2 max_tokens, $3 timeout
  cd $Q; $PY -s run_main.py --url $H --arm $1 --skip-slot --no-think-check --usage --max-tokens $2 --timeout $3 --meta "$META" >> $Q/raw/run_$1.log 2>&1
  log "$1 rc=$? rows=$(( $(wc -l < raw/main_$1.jsonl) - 1 ))"
}
log "chain start"
ssh mark@10.0.0.194 'grep -q -- "--reasoning-budget 0" ~/bench/hymem-1019/serve_flint.sh' || serve "--reasoning-budget 0" NT || { log "ABORT: no budget-0 server"; exit 1; }
if smoke 0 >> $LOG 2>&1; then log "FLNT smoke OK"; run_arm FLNT 1024 600; else log "FLNT SMOKE GATE FAILED: arm not run"; fi
if [ ! -f $Q/raw/FLINT_STOP ]; then
  serve "" TK || { log "ABORT: thinking server did not come up"; exit 1; }
  if smoke 1 >> $LOG 2>&1; then log "FLTK smoke OK"; run_arm FLTK 8192 3600; else log "FLTK SMOKE GATE FAILED: arm not run"; fi
fi
cd $Q; $PY -s analyze_flint.py >> $LOG 2>&1; log "analysis rc=$?"
# wait for the server to EXIT before powering off: s194.sh refuses while any llama-server runs (10-22: it raced the kill)
ssh mark@10.0.0.194 'P=$(cat ~/bench/hymem-1019/server.pid); [ "$(readlink /proc/$P/exe)" = "$HOME/llama.cpp-flint/build_sm60/bin/llama-server" ] && kill $P && timeout 60 tail --pid=$P -f /dev/null'
timeout 120 $R/tools/s194.sh off >> $LOG 2>&1
log "DONE"
