#!/usr/bin/env bash
# PREREG_SCI_DISTILL.md Addendum 2, on the desktop: M1 with thinking on (sampled, K=1). Waits for the GPQA chain
# (sci-distill unit, which powers .194 off), powers .194 on, then Q35BT and DSV9T in turn, each as four shards on four
# single-GPU servers (-np 1); merges the shards, analyses, powers .194 off. Resumable per shard (run_main.py skips ids).
set -uo pipefail
R=/mnt/TG_2TB/Projects/Apollo; SD=$R/data/receipts/sci-distill; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
OUTD=/mnt/TG_2TB/AI/Models/sci-distill-gguf; GB=$OUTD/Qwen3.5-9B-Q8_0.gguf; GF=$OUTD/DSV4P-Qwen3.5-9B-Q8_0.gguf
H=10.0.0.194; RD='~/AI/Models/sci-distill'; BIN='~/llama.cpp-67107ac/build_sm60/bin/llama-server'
LOG=$SD/raw/m1think.log; FLAGS="-ngl 99 -c 20480 -ctk f16 -ctv f16 -np 1 -fit off --jinja --cache-ram 0 --host 0.0.0.0"
SAMP='{"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5}'
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
stop() { ssh "$H" "P=\$(cat ~/sci/srv_$1.pid 2>/dev/null); [ -n \"\$P\" ] && [ \"\$(readlink /proc/\$P/exe)\" = \"\$HOME/llama.cpp-67107ac/build_sm60/bin/llama-server\" ] && kill \$P && timeout 60 tail --pid=\$P -f /dev/null; rm -f ~/sci/srv_$1.pid"; }
stopall() { for p in 8190 8191 8192 8193; do stop $p; done; }
finish() { stopall; timeout 120 "$R/tools/s194.sh" off >> "$LOG" 2>&1; log "== DONE (${1:-0})"; exit "${1:-0}"; }
start() {  # start LABEL FILE GPU PORT (as run_sci_distill.sh)
  ssh "$H" "CUDA_VISIBLE_DEVICES=$3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $RD/$(basename "$2") $FLAGS --port $4 > ~/sci/srv_$4.log 2>&1 < /dev/null & echo \$! > ~/sci/srv_$4.pid"
  local i up=0; for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$4/health" >/dev/null && { up=1; break; }
    ssh "$H" "kill -0 \$(cat ~/sci/srv_$4.pid) 2>/dev/null" || break; done
  [ $up = 1 ] || { log "ABORT: $1 on :$4 not healthy: $(ssh "$H" "tail -n 2 ~/sci/srv_$4.log")"; return 1; }
  local mp; mp=$(curl -s -m 5 "http://$H:$4/props" | "$PY" -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$2")" ] || { log "ABORT: $1 :$4 WRONG SERVER: $mp"; return 1; }
  ssh "$H" "tr '\0' ' ' < /proc/\$(cat ~/sci/srv_$4.pid)/cmdline" | grep -q -- "$FLAGS" || { log "ABORT: $1 :$4 flags not on the command line"; return 1; }
}

while systemctl --user is-active -q sci-distill; do sleep 60; done
log "GPQA chain ended: $(tail -n 1 "$SD/raw/chain.log")"; sleep 90
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$H" true 2>/dev/null; then
  for i in $(seq 1 30); do "$R/tools/s194.sh" status 2>/dev/null | grep -q 'chassis : off' && break; sleep 10; done
  "$R/tools/s194.sh" on >> "$LOG" 2>&1 || { log "ABORT: .194 did not come up"; exit 1; }
fi
ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "ABORT: a llama-server is already running on .194"; exit 1; }
for f in "$GB" "$GF"; do want=$(sha256sum "$f" | cut -d' ' -f1); got=$(ssh "$H" "sha256sum $RD/$(basename "$f")" | cut -d' ' -f1)
  [ "$got" = "$want" ] || { log "ABORT: HASH MISMATCH $(basename "$f") on .194"; finish 1; }; done
log "files verified on .194; GPUs: $(ssh "$H" 'nvidia-smi --query-gpu=index,power.limit,clocks.applications.graphics --format=csv,noheader' | tr '\n' ';')"
var=$("$PY" -c 'import json,sys; print(json.dumps(json.loads(open(sys.argv[1]).readline())["variant_ids"]))' "$QA/raw/main_Q35B.jsonl")
tail=$("$PY" -c 'import json,sys; sys.stdout.write(json.loads(open(sys.argv[1]).readline())["render_tail"])' "$QA/raw/main_Q35B.jsonl"; printf x); tail=${tail%x}

for spec in "Q35BT|$GB" "DSV9T|$GF"; do IFS='|' read -r ARM F <<< "$spec"; SHA=$(sha256sum "$F" | cut -d' ' -f1)
  [ -s "$QA/raw/main_$ARM.jsonl" ] && { log "$ARM already merged, skipping"; continue; }
  start $ARM "$F" 0 8190 && start $ARM "$F" 1 8191 && start $ARM "$F" 2 8192 && start $ARM "$F" 3 8193 || finish 1
  r=$(curl -s -m 1800 "http://$H:8190/v1/chat/completions" -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"What is 17*19? Answer briefly."}],"temperature":1.0,"top_p":0.95,"top_k":20,"min_p":0,"presence_penalty":1.5,"seed":1,"max_tokens":8192,"cache_prompt":false,"chat_template_kwargs":{"enable_thinking":true}}' \
      | python3 -c "import sys,json; m=json.load(sys.stdin)['choices'][0]['message']; c=len(m.get('content') or ''); r=len(m.get('reasoning_content') or ''); print('content',c,'reasoning',r); sys.exit(0 if c and r else 1)") \
    || { log "ABORT: $ARM thinking smoke failed: $r"; finish 1; }
  log "$ARM: four servers up, smoke OK ($r)"
  for k in 0 1 2 3; do
    meta=$("$PY" -c 'import json,sys; print(json.dumps(dict(zip(["arm","model","sha256","commit","flags","env","host","prereg"], sys.argv[1:]))))' \
      "$ARM.s$k" "$(basename "$F")" "$SHA" 67107ac34f "$FLAGS --port $((8190 + k))" "CUDA_VISIBLE_DEVICES=$k GGML_CUDA_ALLREDUCE=internal" ".194 single P100" "PREREG_SCI_DISTILL.md Addendum 2")
    (cd "$QA" && "$PY" run_main.py --url "http://$H:$((8190 + k))" --arm "$ARM.s$k" --shard "$k/4" --usage --thinking --sampling "$SAMP" \
       --max-tokens 16384 --timeout 3600 --meta "$meta" --expect-variants "$var" --expect-render-tail "$tail") >> "$SD/raw/logs/m1think_$ARM.s$k.log" 2>&1 &
  done
  wait
  n=0; for k in 0 1 2 3; do n=$(( n + $(wc -l < "$QA/raw/main_$ARM.s$k.jsonl") - 1 )); done; log "$ARM: $n rows in four shards"
  stopall
  [ "$n" = 240 ] && (cd "$QA" && "$PY" merge_shards.py "$ARM" 4) >> "$LOG" 2>&1 || log "$ARM: NOT merged ($n rows)"
done
{ echo "== M1 thinking on: DSV9T vs Q35BT"; "$PY" "$QA/../ds41-h2h/analyze_ds41.py" DSV9T Q35BT --json "$SD/RESULT_m1_thinking.json"; } >> "$LOG" 2>&1
log "analysis rc=$?"
finish 0
