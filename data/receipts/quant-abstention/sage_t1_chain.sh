#!/bin/bash
# PREREG_SAGE.md Addendum 1: SGTHK1 and SGVER1 (Sage's recommended sampling). Waits until the registered chain (sage-chain
# unit) has finished and powered .194 off, powers it on again, stages Sage in /dev/shm, runs both arms, analyses, powers off.
set -u
R=/mnt/TG_2TB/Projects/Apollo; PY=$R/venv_cachyos/bin/python3; Q=$R/data/receipts/quant-abstention; H=http://10.0.0.194:8190
LOG=$Q/raw/sage_t1_state.log; S194=mark@10.0.0.194; SYS="You are a helpful assistant."
SAMP='{"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5}'
SRC=/mnt/TG_2TB/models_small/sage-a1.5/Sage-A1.5-Q8_0.gguf; SHA=f7247f6faef3f6c616b953595e1fc7c3fbf257d02d9915af5fdf15e808ea8ee4
log () { echo "$(date '+%F %T') $*" >> $LOG; }
log "waiting for sage-chain"
while systemctl --user is-active -q sage-chain; do sleep 60; done
log "sage-chain finished: $(tail -1 $Q/raw/sage_state.log)"; sleep 120
timeout 300 $R/tools/s194.sh on >> $LOG 2>&1
for i in $(seq 1 60); do ssh -o ConnectTimeout=5 -o BatchMode=yes $S194 true 2>/dev/null && break; sleep 10; done
ssh -o ConnectTimeout=5 $S194 true || { log "ABORT: .194 did not come up"; exit 1; }
rsync -a $SRC $S194:/dev/shm/ && got=$(ssh $S194 'sha256sum /dev/shm/Sage-A1.5-Q8_0.gguf' | cut -d' ' -f1)
[ "${got:-}" = $SHA ] || { log "ABORT: staged sha256 mismatch (${got:-none})"; timeout 120 $R/tools/s194.sh off >> $LOG 2>&1; exit 1; }
log "staged, sha256 ok; clocks $(ssh $S194 'nvidia-smi --query-gpu=clocks.applications.graphics,power.limit --format=csv,noheader | tr "\n" " "')"
ssh $S194 "nohup ~/bench/sage/serve_sage.sh /dev/shm/Sage-A1.5-Q8_0.gguf > ~/bench/sage/server_SAGE_T1.log 2>&1 < /dev/null & echo \$! > ~/bench/sage/server.pid"
ok=0; for i in $(seq 1 120); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && { ok=1; break; }; done
[ $ok = 1 ] || { log "ABORT: server did not come up"; timeout 120 $R/tools/s194.sh off >> $LOG 2>&1; exit 1; }
on=$(curl -s $H/apply-template -H 'Content-Type: application/json' -d "{\"messages\":[{\"role\":\"system\",\"content\":\"$SYS\"},{\"role\":\"user\",\"content\":\"Q\"}],\"chat_template_kwargs\":{\"verification\":true}}" | grep -c 'Verification protocol: enabled')
off=$(curl -s $H/apply-template -H 'Content-Type: application/json' -d "{\"messages\":[{\"role\":\"system\",\"content\":\"$SYS\"},{\"role\":\"user\",\"content\":\"Q\"}],\"chat_template_kwargs\":{\"verification\":false}}" | grep -c 'Verification protocol')
log "server up; template check: with flag $on (want 1), without $off (want 0)"
META='{"model": "Sage-A1.5 Q8_0 (InternScience official, sha256 f7247f6f..., rev 1cbe2925)", "build": "llama.cpp c7fc509 build_sm60 gcc-13", "placement": "-ngl 99 -sm layer -c 16384 -ctk f16 -ctv f16 -np 1 -fit off, /dev/shm", "template": "gguf"}'
cd $Q
if [ "$on" = 1 ] && [ "$off" = 0 ]; then
  for V in false true; do A=SGTHK1; [ $V = true ] && A=SGVER1
    $PY -s run_main.py --url $H --arm $A --usage --thinking --system "$SYS" --template-kwargs "{\"verification\": $V}" --sampling "$SAMP" \
      --max-tokens 8192 --timeout 1800 --meta "$META" >> raw/run_$A.log 2>&1
    log "$A rc=$? rows=$(( $(wc -l < raw/main_$A.jsonl) - 1 ))"
  done
  $PY -s analyze_sage_t1.py >> $LOG 2>&1; log "analysis rc=$?"
else log "ABORT: template check failed"; fi
ssh $S194 'P=$(cat ~/bench/sage/server.pid); [ "$(readlink /proc/$P/exe)" = "$HOME/llama.cpp-flint/build_sm60/bin/llama-server" ] && kill $P && timeout 60 tail --pid=$P -f /dev/null; rm -f /dev/shm/Sage-A1.5-Q8_0.gguf'
timeout 120 $R/tools/s194.sh off >> $LOG 2>&1
log "DONE"
