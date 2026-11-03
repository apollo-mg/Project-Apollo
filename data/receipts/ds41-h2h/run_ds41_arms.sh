#!/usr/bin/env bash
# PREREG_DS41_H2H.md: arms DS41G (ISTA GSQ-RCO IQ2_XXS) -> DS41U (Unsloth UD-IQ1_M) -> DS41GR (DS41G replayed on M1R20, a
# fresh server, same placement). Runs on the desktop; the servers run on .194 (all four P100s), one at a time, each fresh
# and verified. Resumable: run_main.py skips ids already written. Powers .194 off after a complete run.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; QA="$HERE/../quant-abstention"; ROOT="$(cd "$HERE/../../.." && pwd)"
PY=$ROOT/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"
BIN='~/llama.cpp-b12063/build_sm60/bin/llama-server'
D='~/AI/Models/ds41'
G="$D/gsq/DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00001-of-00006.gguf"
U="$D/unsloth/DeepSeek-V4.1-Flash-1017-UD-IQ1_M-00001-of-00005.gguf"
TPL="$D/gsq/chat_template.jinja"      # one template for both arms (sha256 4d61d22c...; renders M1 the same as both embedded ones)
CPU_LAYERS="2|3|4|5|6|7|8|9|13|14|15|16|17|18|19|23|24|25|26|27|28|29|34|35|36|37|38|39"   # as smoke_ds41.sh
OT="blk\\.($CPU_LAYERS)\\.ffn_(up|down|gate)_exps=CPU"
FLAGS="-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off --cache-ram 0 --numa distribute --reasoning off --host 0.0.0.0 --port $PORT"
RUNARGS="--skip-slot --usage --timeout 3600 --neutral-penalties"
mkdir -p "$QA/raw/logs"; LOG="$QA/raw/logs/ds41_arms.log"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

stop_server() {    # exact process name; nothing else on .194 runs llama-server (checked 11-03)
  ssh "$H" 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' \
    || { log "a llama-server survived pkill -- aborting"; exit 1; }
}

start_server() {   # start_server ARM MODEL -> 0 verified; 1 died or never healthy; 2 the wrong server or placement
  local arm=$1 model=$2
  stop_server
  ssh "$H" "GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $model --chat-template-file $TPL -ot '$OT' $FLAGS > ~/ds41_$arm.log 2>&1 < /dev/null &"
  local up=0
  for i in $(seq 1 300); do
    sleep 5
    ssh "$H" 'pgrep -x llama-server >/dev/null' || { log "$arm: server died: $(ssh "$H" "tail -3 ~/ds41_$arm.log")"; return 1; }
    curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }
  done
  [ $up = 1 ] || { log "$arm: not healthy after 1500 s"; return 1; }
  local mp ov mem cmd
  mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$model")" ] || { log "$arm: WRONG SERVER answered: $mp"; return 2; }
  ov=$(ssh "$H" "grep -c 'tensor overrides to CPU are used' ~/ds41_$arm.log")
  [ "$ov" -ge 1 ] || { log "$arm: -ot NOT in effect"; return 2; }
  mem=$(ssh "$H" 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits' | tr '\n' ' ')
  for m in $mem; do [ "$m" -ge 8000 ] || { log "$arm: a GPU holds only $m MiB -- placement wrong: $mem"; return 2; }; done
  cmd=$(ssh "$H" 'tr "\0" " " < /proc/$(pgrep -x llama-server)/cmdline')
  case "$cmd" in *"--chat-template-file"*chat_template.jinja*"-ot"*) ;; *) log "$arm: command line lacks the template or -ot: $cmd"; return 2;; esac
  log "$arm: verified -- serving $(basename "$mp"), GPU MiB $mem, override line present, pid $(ssh "$H" 'pgrep -x llama-server')"
  return 0
}

gate() {           # the rendered-and-tokenized M1 prompts, one hash; every arm must match DS41G's
  local arm=$1 h; h=$($PY "$HERE/prompt_gate.py" "$URL") || { log "$arm: prompt gate failed to run"; return 1; }
  log "$arm: prompt gate $h"
  if [ "$arm" = DS41G ]; then echo "$h" > "$QA/raw/logs/ds41_gate_DS41G.txt"
  elif [ "$h" != "$(cat "$QA/raw/logs/ds41_gate_DS41G.txt")" ]; then log "$arm: PROMPTS DIFFER from DS41G -- aborting"; return 1; fi
}

run_arm() {        # run_arm ARM MODEL [CORPUS]
  local arm=$1 model=$2 corpus=${3:-M1}
  gate "$arm" || exit 1
  local gpus shas tsha meta extra=""
  gpus=$(ssh "$H" 'nvidia-smi --query-gpu=index,power.limit,clocks.applications.graphics,clocks.sm,memory.used --format=csv,noheader' | tr '\n' ';')
  shas=$(ssh "$H" "cat $(dirname "$model")/*.gguf.verified" | cut -c1-16 | tr '\n' ',')
  tsha=$(ssh "$H" "sha256sum $TPL" | cut -c1-16)
  meta=$($PY -c 'import json,sys; print(json.dumps(dict(zip(["arm","model","sha256_prefixes","build","flags","ot","template","template_sha256","gpus","host"], sys.argv[1:]))))' \
         "$arm" "$model" "$shas" "llama.cpp b12063 2cbca389 build_sm60" "$FLAGS" "$OT" "$TPL" "$tsha" "$gpus" ".194 4xP100")
  if [ "$arm" != DS41G ]; then   # the variant ids and render tail must be DS41G's (files: the tail may hold a newline)
    $PY -c 'import json,sys; h=json.loads(open(sys.argv[1]).readline()); open(sys.argv[2],"w").write(json.dumps(h["variant_ids"])); open(sys.argv[3],"w").write(h["render_tail"])' \
      "$QA/raw/main_DS41G.jsonl" "$QA/raw/logs/ds41_expect_variants.json" "$QA/raw/logs/ds41_expect_tail.txt" || { log "$arm: cannot read DS41G's header"; exit 1; }
    extra=1
  fi
  log "$arm: running $corpus"
  if [ -n "$extra" ]; then
    $PY "$QA/run_main.py" --url "$URL" --arm "$arm" --corpus "$corpus" --meta "$meta" $RUNARGS \
      --expect-variants "$(cat "$QA/raw/logs/ds41_expect_variants.json")" --expect-render-tail "$(cat "$QA/raw/logs/ds41_expect_tail.txt")" >> "$LOG" 2>&1
  else
    $PY "$QA/run_main.py" --url "$URL" --arm "$arm" --corpus "$corpus" --meta "$meta" $RUNARGS >> "$LOG" 2>&1
  fi
  log "$arm: run_main exit $?"
}

rows() { local f="$QA/raw/main_$1.jsonl"; [ "$2" != M1 ] && f="$QA/raw/main_$1.$2.jsonl"; [ -f "$f" ] && echo $(($(wc -l < "$f") - 1)) || echo 0; }
log "== ds41 arms start"
for spec in "DS41G|$G|M1|240" "DS41U|$U|M1|240" "DS41GR|$G|M1R20|20"; do
  IFS='|' read -r arm model corpus want <<< "$spec"
  if [ "$(rows "$arm" "$corpus")" -ge "$want" ]; then log "$arm: already complete, skipped"; continue; fi
  start_server "$arm" "$model"; rc=$?
  [ $rc = 2 ] && { log "abort: wrong server or placement"; exit 1; }
  [ $rc = 0 ] || { log "$arm failed to start -- aborting"; exit 1; }
  run_arm "$arm" "$model" "$corpus"
  [ "$(rows "$arm" "$corpus")" -ge "$want" ] || { log "$arm: only $(rows "$arm" "$corpus") of $want rows -- aborting"; exit 1; }
done
stop_server
log "== ds41 arms done; powering .194 off"
"$ROOT/tools/s194.sh" off >> "$LOG" 2>&1
