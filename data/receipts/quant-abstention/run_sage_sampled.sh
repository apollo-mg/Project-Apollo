#!/bin/bash
# PREREG_SAGE_SAMPLED.md, on the desktop: a procedural copy of run_sage_matched.sh with Sage's recommended sampling and
# three seeds. Powers .194 on, then Q36BS1-3 (base Q6_K) and SGQ6S1-3 (Sage-A1.5 Q6_K) on all four P100s via
# ~/bench/sage/serve_sage.sh, weights from /dev/shm one model at a time; the token prompt gate must match across models;
# analysis (analyze_k.py); .194 powered off. Resumable: run_main.py skips ids already written.
set -u
R=/mnt/TG_2TB/Projects/Apollo; PY=$R/venv_cachyos/bin/python3; Q=$R/data/receipts/quant-abstention; H=http://10.0.0.194:8190
LOG=$Q/raw/sage_sampled.log; S194=mark@10.0.0.194; GATE=$Q/../ds41-h2h/prompt_gate.py
BASE_SRC=/mnt/HDD/from_73_20260827/models/Qwen3.6-35B-A3B-Q6_K.gguf; BASE_SHA=0e0e2c376d683e84886a08ddd19b071a8173caa2afac94d3727bb0a7c4bb22e8
SAGE_SRC=/mnt/HDD/Models/sage-a15-q6/Sage-A1.5.Q6_K.gguf; SAGE_SHA=852dffdde471f41b15c264c35944e1ca8b380e68e823679ea816f3ca664b2fe4
SAMP='{"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5}'
log () { echo "$(date '+%F %T') $*" >> $LOG; }
finish () { timeout 120 $R/tools/s194.sh off >> $LOG 2>&1; log "DONE"; exit "${1:-0}"; }

# 0. .194 up and idle
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes $S194 true 2>/dev/null; then
  $R/tools/s194.sh on >> $LOG 2>&1 || { log "ABORT: .194 did not come up"; exit 1; }
fi
ssh $S194 'pgrep -x llama-server >/dev/null' && { log "ABORT: a llama-server is already running on .194"; exit 1; }
log "chain start; .194 up: $(ssh $S194 'uptime -p; nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | tr "\n" " "')"
$PY -c 'import json,sys; h=json.loads(open(sys.argv[1]).readline()); open(sys.argv[2],"w").write(json.dumps(h["variant_ids"])); open(sys.argv[3],"w").write(h["render_tail"])' \
  "$Q/raw/main_Q36B.jsonl" "$Q/raw/logs/ss_expect_variants.json" "$Q/raw/logs/ss_expect_tail.txt"

serve () {   # $1 model on .194, $2 label -- as run_sage_matched.sh
  ssh $S194 "nohup ~/bench/sage/serve_sage.sh $1 > ~/bench/sage/server_$2.log 2>&1 < /dev/null & echo \$! > ~/bench/sage/server.pid"
  for i in $(seq 1 120); do sleep 5; curl -s -m 3 $H/health | grep -q '"ok"' && break
    ssh $S194 'kill -0 $(cat ~/bench/sage/server.pid) 2>/dev/null' || { log "ABORT: $2 server died: $(ssh $S194 "tail -2 ~/bench/sage/server_$2.log")"; return 1; }; done
  local mp; mp=$(curl -s -m 5 $H/props | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$mp" = "$1" ] || { log "ABORT: $2 WRONG SERVER answered: $mp"; return 1; }
  ssh $S194 'tr "\0" " " < /proc/$(cat ~/bench/sage/server.pid)/cmdline' | grep -q -- '-ctk f16 -ctv f16' || { log "ABORT: $2 f16 KV flags not on the command line"; return 1; }
  log "$2 server up, serving $mp: $(ssh $S194 'nvidia-smi --query-gpu=memory.used,clocks.sm --format=csv,noheader | tr "\n" " "')"
}
stopsrv () { ssh $S194 'P=$(cat ~/bench/sage/server.pid); [ "$(readlink /proc/$P/exe)" = "$HOME/llama.cpp-flint/build_sm60/bin/llama-server" ] && kill $P && timeout 60 tail --pid=$P -f /dev/null'; }
smoke () {   # thinking off: non-empty content, empty reasoning
  curl -s -m 1200 $H/v1/chat/completions -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"What is 17*19? Answer briefly."}],"temperature":0,"max_tokens":4096,"cache_prompt":false,"chat_template_kwargs":{"enable_thinking":false}}' \
  | python3 -c "import sys,json; m=json.load(sys.stdin)['choices'][0]['message']; c=len(m.get('content') or ''); r=len(m.get('reasoning_content') or ''); print('content',c,'reasoning',r); sys.exit(0 if c and r==0 else 1)"
}
stage () {   # $1 local file, $2 sha256 -> /dev/shm on .194, hash verified
  local f=/dev/shm/$(basename "$1")
  ssh $S194 'rm -f /dev/shm/Qwen3.6-35B-A3B-Q6_K.gguf /dev/shm/Sage-A1.5.Q6_K.gguf'; rsync -a "$1" $S194:/dev/shm/ || { log "ABORT: copy of $1 failed"; return 1; }
  local got; got=$(ssh $S194 "sha256sum $f" | cut -d' ' -f1); [ "$got" = "$2" ] || { log "ABORT: HASH MISMATCH $f: $got"; return 1; }
  log "staged $f, sha256 verified"
}
META () { echo "{\"model\": \"$1\", \"build\": \"llama.cpp c7fc509 build_sm60 gcc-13\", \"placement\": \"-ngl 99 -sm layer -c 16384 -ctk f16 -ctv f16 -np 1 -fit off, /dev/shm\", \"template\": \"gguf\", \"prereg\": \"PREREG_SAGE_SAMPLED.md\"}"; }
arm () {     # $1 arm, $2 model description, $3 seed base
  local tail; tail=$(cat "$Q/raw/logs/ss_expect_tail.txt"; printf x); tail=${tail%x}   # $(cat) would strip "\n\n"
  local r; if r=$(smoke); then log "$1 smoke OK: $r"; else log "ABORT: $1 SMOKE FAILED: $r"; return 1; fi
  (cd $Q && $PY -s run_main.py --url $H --arm $1 --usage --max-tokens 1024 --timeout 600 --sampling "$SAMP" --seed-base $3 --meta "$(META "$2")" \
    --expect-variants "$(cat "$Q/raw/logs/ss_expect_variants.json")" --expect-render-tail "$tail" >> raw/run_$1.log 2>&1)
  log "$1 rc=$? rows=$(( $(wc -l < $Q/raw/main_$1.jsonl) - 1 ))"
}

# 1. the base, three seeds on one server load
stage "$BASE_SRC" $BASE_SHA || finish 1
serve /dev/shm/Qwen3.6-35B-A3B-Q6_K.gguf BASE_S || { stopsrv; finish 1; }
gb=$($PY "$GATE" $H); log "prompt gate base: $gb"
for r in 1 2 3; do arm Q36BS$r "Qwen3.6-35B-A3B Q6_K (mradermacher static, sha256 0e0e2c37...)" $((20261111 + r)) || { stopsrv; finish 1; }; done
stopsrv

# 2. Sage, the same three seeds
stage "$SAGE_SRC" $SAGE_SHA || finish 1
serve /dev/shm/Sage-A1.5.Q6_K.gguf SAGE_S || { stopsrv; finish 1; }
gs=$($PY "$GATE" $H); log "prompt gate Sage: $gs"
[ -n "$gb" ] && [ "$gs" = "$gb" ] || { log "ABORT: PROMPTS DIFFER (base $gb, Sage $gs)"; stopsrv; finish 1; }
for r in 1 2 3; do arm SGQ6S$r "Sage-A1.5 Q6_K (mradermacher static, rev fedd56b6, sha256 852dffdd...)" $((20261111 + r)) || { stopsrv; finish 1; }; done
stopsrv
ssh $S194 'rm -f /dev/shm/Qwen3.6-35B-A3B-Q6_K.gguf /dev/shm/Sage-A1.5.Q6_K.gguf'

# 3. analysis
$PY $Q/analyze_k.py --a Q36BS1,Q36BS2,Q36BS3 --b SGQ6S1,SGQ6S2,SGQ6S3 --a-greedy Q36B2 --b-greedy SGQ6 --json $Q/RESULT_sage_sampled.json >> $LOG 2>&1
log "analysis rc=$?"
finish 0
