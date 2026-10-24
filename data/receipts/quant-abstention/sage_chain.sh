#!/bin/bash
# PREREG_SAGE.md: SGOFF, SGTHK, SGVER on Sage-A1.5 Q8_0, then Q36B on the Qwen3.6-35B-A3B Q6_K base, all on .194; analysis;
# .194 powered off. Usage: sage_chain.sh [SAGE_TEMPLATE_FILE_ON_194]  (empty = the GGUF's own template)
set -u
R=/mnt/TG_2TB/Projects/Apollo; PY=$R/venv_cachyos/bin/python3; Q=$R/data/receipts/quant-abstention; H=http://10.0.0.194:8190
LOG=$Q/raw/sage_state.log; S194=mark@10.0.0.194; TPL=${1:-}; SYS="You are a helpful assistant."
BASE_SRC="/mnt/HDD/from_73_20260827/models/Qwen3.6-35B-A3B-Q6_K.gguf"
log () { echo "$(date '+%F %T') $*" >> $LOG; }
serve () {   # $1 model on .194, $2 label, $3 template file (optional)
  ssh $S194 "nohup ~/bench/sage/serve_sage.sh $1 $3 > ~/bench/sage/server_$2.log 2>&1 < /dev/null & echo \$! > ~/bench/sage/server.pid"
  for i in $(seq 1 120); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && { log "$2 server up: $(ssh $S194 'nvidia-smi --query-gpu=memory.used,clocks.sm --format=csv,noheader | tr "\n" " "')"; return 0; }
    ssh $S194 'kill -0 $(cat ~/bench/sage/server.pid) 2>/dev/null' || break; done
  log "ABORT: $2 server did not come up"; return 1
}
stopsrv () { ssh $S194 'P=$(cat ~/bench/sage/server.pid); [ "$(readlink /proc/$P/exe)" = "$HOME/llama.cpp-flint/build_sm60/bin/llama-server" ] && kill $P && timeout 60 tail --pid=$P -f /dev/null'; }
smoke () {   # $1 thinking true|false, $2 extra JSON fields; prints content/reasoning lengths, fails on empty content or thinking-off reasoning
  curl -s -m 1200 $H/v1/chat/completions -H 'Content-Type: application/json' -d "{\"messages\":[$2{\"role\":\"user\",\"content\":\"What is 17*19? Answer briefly.\"}],\"temperature\":0,\"max_tokens\":4096,\"cache_prompt\":false,\"chat_template_kwargs\":{\"enable_thinking\":$1$3}}" \
  | python3 -c "import sys,json; m=json.load(sys.stdin)['choices'][0]['message']; c=len(m.get('content') or ''); r=len(m.get('reasoning_content') or ''); print('content',c,'reasoning',r); sys.exit(0 if c and ('$1'=='true' or r==0) else 1)"
}
META () { echo "{\"model\": \"$1\", \"build\": \"llama.cpp c7fc509 build_sm60 gcc-13\", \"placement\": \"-ngl 99 -sm layer -c 16384 -ctk f16 -ctv f16 -np 1 -fit off, /dev/shm\", \"template\": \"${TPL:-gguf}\"}"; }
log "chain start (template: ${TPL:-gguf})"
serve /dev/shm/Sage-A1.5-Q8_0.gguf SAGE "$TPL" || exit 1
on=$(curl -s $H/apply-template -H 'Content-Type: application/json' -d "{\"messages\":[{\"role\":\"system\",\"content\":\"$SYS\"},{\"role\":\"user\",\"content\":\"Q\"}],\"chat_template_kwargs\":{\"verification\":true}}" | grep -c 'Verification protocol: enabled')
off=$(curl -s $H/apply-template -H 'Content-Type: application/json' -d "{\"messages\":[{\"role\":\"system\",\"content\":\"$SYS\"},{\"role\":\"user\",\"content\":\"Q\"}],\"chat_template_kwargs\":{\"verification\":false}}" | grep -c 'Verification protocol')
log "template check: trigger with flag $on (want 1), without $off (want 0)"
[ "$on" = 1 ] && [ "$off" = 0 ] || { log "ABORT: template check failed"; stopsrv; timeout 120 $R/tools/s194.sh off >> $LOG 2>&1; exit 1; }
SM="Sage-A1.5 Q8_0 (InternScience official, sha256 f7247f6f..., rev 1cbe2925)"
cd $Q
if r=$(smoke false "" ""); then log "SGOFF smoke OK: $r"
  $PY -s run_main.py --url $H --arm SGOFF --usage --max-tokens 1024 --timeout 600 --meta "$(META "$SM")" >> raw/run_SGOFF.log 2>&1
  log "SGOFF rc=$? rows=$(( $(wc -l < raw/main_SGOFF.jsonl) - 1 ))"; else log "SGOFF SMOKE FAILED: $r"; fi
SYSJ="{\"role\":\"system\",\"content\":\"$SYS\"},"
for V in false true; do A=SGTHK; [ $V = true ] && A=SGVER
  if r=$(smoke true "$SYSJ" ",\"verification\":$V"); then log "$A smoke OK: $r"
    $PY -s run_main.py --url $H --arm $A --usage --thinking --system "$SYS" --template-kwargs "{\"verification\": $V}" --max-tokens 8192 --timeout 1800 --meta "$(META "$SM")" >> raw/run_$A.log 2>&1
    log "$A rc=$? rows=$(( $(wc -l < raw/main_$A.jsonl) - 1 ))"; else log "$A SMOKE FAILED: $r"; fi
done
stopsrv; ssh $S194 'rm -f /dev/shm/Sage-A1.5-Q8_0.gguf'
rsync -a "$BASE_SRC" $S194:/dev/shm/ && log "base copied: $(ssh $S194 'sha256sum /dev/shm/Qwen3.6-35B-A3B-Q6_K.gguf')"
if serve /dev/shm/Qwen3.6-35B-A3B-Q6_K.gguf BASE ""; then
  if r=$(smoke false "" ""); then log "Q36B smoke OK: $r"
    $PY -s run_main.py --url $H --arm Q36B --usage --max-tokens 1024 --timeout 600 --meta "$(META "Qwen3.6-35B-A3B Q6_K (plain, NAS from_73_20260827)")" >> raw/run_Q36B.log 2>&1
    log "Q36B rc=$? rows=$(( $(wc -l < raw/main_Q36B.jsonl) - 1 ))"; else log "Q36B SMOKE FAILED: $r"; fi
  stopsrv
fi
ssh $S194 'rm -f /dev/shm/Qwen3.6-35B-A3B-Q6_K.gguf'
$PY -s analyze_sage.py >> $LOG 2>&1; log "analysis rc=$?"
timeout 120 $R/tools/s194.sh off >> $LOG 2>&1
log "DONE"
