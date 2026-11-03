#!/usr/bin/env bash
# PREREG_QWOPUS_CODER.md: QWC (Qwopus Coder Flash Q8_0, GPUs 0+1, :8190) and C.R (base Q8_0 replay, GPUs 2+3, :8191) at
# the same time on .194, as the main campaign's ceiling arm. Runs on the desktop. Resumable (run_main.py skips ids written).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; QA="$HERE/../quant-abstention"; ROOT="$(cd "$HERE/../../.." && pwd)"
PY=$ROOT/venv_cachyos/bin/python3; H=10.0.0.194
BIN='~/buun-0b278/build_sm60/bin/llama-server'
DIR='~/AI/Models/qwopus'
QWC_F="$DIR/Qwopus3.8-27B-Coder-Flash-Q8_0.gguf"; BASE_F="$DIR/Qwen3.8-27B-Q8_0.gguf"
QWC_SHA=d1262b7bfe510a9d7ba5fce5f635febaba8550636e646d7ebd98bc0957f29e29
BASE_SHA=a680f44a06920e5d689774823782006aa3acc8db95750323373b24139b67e348
FLAGS="-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0"
LOG="$QA/raw/logs/qwopus.log"; mkdir -p "$QA/raw/logs"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

# gates before any server: both files' hashes, and the Qwopus template byte-identical to the base's
for spec in "$QWC_F|$QWC_SHA" "$BASE_F|$BASE_SHA"; do
  IFS='|' read -r f want <<< "$spec"
  got=$(ssh "$H" "sha256sum $f" | cut -d' ' -f1)
  [ "$got" = "$want" ] || { log "HASH MISMATCH $f: $got"; exit 1; }
done
log "hashes verified"
ssh "$H" "python3 -I - $QWC_F $BASE_F" <<'EOF' || { log "TEMPLATES DIFFER (or could not be read) -- aborting"; exit 1; }
import sys, os
sys.path.insert(0, os.path.expanduser("~/llama.cpp-b12063/gguf-py")); import gguf
t = [gguf.GGUFReader(os.path.expanduser(p)).fields["tokenizer.chat_template"].contents() for p in sys.argv[1:3]]
print("template chars", len(t[0]), len(t[1])); sys.exit(0 if t[0] == t[1] else 1)
EOF
log "templates identical"
$PY -c 'import json,sys; h=json.loads(open(sys.argv[1]).readline()); open(sys.argv[2],"w").write(json.dumps(h["variant_ids"])); open(sys.argv[3],"w").write(h["render_tail"])' \
  "$QA/raw/main_C.A.jsonl" "$QA/raw/logs/qw_expect_variants.json" "$QA/raw/logs/qw_expect_tail.txt"

ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "a llama-server is already running on .194 -- aborting"; exit 1; }
start() {   # start ARM FILE GPUS PORT
  ssh "$H" "CUDA_VISIBLE_DEVICES=$3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $2 $FLAGS --port $4 > ~/qw_$1.log 2>&1 < /dev/null &"
}
verify() {  # verify ARM FILE PORT
  local i up=0
  for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$3/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "$1: not healthy after 600 s: $(ssh "$H" "tail -2 ~/qw_$1.log")"; return 1; }
  local mp; mp=$(curl -s -m 5 "http://$H:$3/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$2")" ] || { log "$1: WRONG SERVER answered: $mp"; return 1; }
  ssh "$H" "grep -q 'K (f16).*V (f16)' ~/qw_$1.log" || { log "$1: f16 KV line not found"; return 1; }
  log "$1: verified -- serving $(basename "$mp") on :$3"
}
start QWC "$QWC_F" 0,1 8190; start C.R "$BASE_F" 2,3 8191
verify QWC "$QWC_F" 8190 && verify C.R "$BASE_F" 8191 || { ssh "$H" 'pkill -x llama-server'; exit 1; }
log "GPUs: $(ssh "$H" 'nvidia-smi --query-gpu=index,power.limit,clocks.applications.graphics,memory.used --format=csv,noheader' | tr '\n' ';')"

run() {     # run ARM FILE GPUS PORT SHA
  # $(cat) strips trailing newlines, and C.A's render tail ends in "\n\n": read it with a sentinel (11-03, first launch
  # stopped at the runner's tail check on both lanes before writing any row)
  local tail; tail=$(cat "$QA/raw/logs/qw_expect_tail.txt"; printf x); tail=${tail%x}
  local meta; meta=$($PY -c 'import json,sys; print(json.dumps(dict(zip(["arm","model","sha256","commit","flags","env","host"], sys.argv[1:]))))' \
    "$1" "$2" "$5" 0b2789f23f5ac10ed9a99aeb40ed10d3ba1c0163 "$FLAGS --port $4" "CUDA_VISIBLE_DEVICES=$3 GGML_CUDA_ALLREDUCE=internal" ".194")
  $PY "$QA/run_main.py" --url "http://$H:$4" --arm "$1" --meta "$meta" --usage \
    --expect-variants "$(cat "$QA/raw/logs/qw_expect_variants.json")" --expect-render-tail "$tail" \
    > "$QA/raw/logs/qw_run_$1.log" 2>&1
  log "$1: run_main exit $? ($(( $(wc -l < "$QA/raw/main_$1.jsonl") - 1 )) rows)"
}
log "running both lanes"
run QWC "$QWC_F" 0,1 8190 "$QWC_SHA" & run C.R "$BASE_F" 2,3 8191 "$BASE_SHA" & wait
ssh "$H" 'pkill -x llama-server'
log "== done"
