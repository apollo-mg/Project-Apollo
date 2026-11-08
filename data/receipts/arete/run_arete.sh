#!/usr/bin/env bash
# PREREG_ARETE.md, on the desktop: after download_arete.sh, convert Arete-27B to Q8_0 (llama.cpp 67107ac34f), record the
# tensor-type map against the base Q8_0, stage it on .194 (hash checked there), then run ARE (GPUs 0+1, :8190) and C.R2
# (base replay, GPUs 2+3, :8191) at the same time as qwopus/run_qwopus.sh did, gated on identical prompt tokens.
# Stops the servers and powers .194 off. Resumable: run_main.py skips ids already written; staging steps skip if done.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; QA="$HERE/../quant-abstention"; ROOT="$(cd "$HERE/../../.." && pwd)"
PY=$ROOT/venv_cachyos/bin/python3; LC=$ROOT/engines/llama_cpp_67107ac; H=10.0.0.194
SRC=/mnt/TG_2TB/AI/Models/arete-27b; OUTD=/mnt/TG_2TB/AI/Models/arete-27b-gguf; OUT=$OUTD/Arete-27B-Q8_0.gguf
BASE_LOCAL=/mnt/TG_2TB/AI/Models/qwen38-27b-ref/Qwen3.8-27B-Q8_0.gguf
BIN='~/buun-0b278/build_sm60/bin/llama-server'; DIR='~/AI/Models/qwopus'
ARE_F="$DIR/Arete-27B-Q8_0.gguf"; BASE_F="$DIR/Qwen3.8-27B-Q8_0.gguf"
BASE_SHA=a680f44a06920e5d689774823782006aa3acc8db95750323373b24139b67e348
FLAGS="-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0"
LOG="$QA/raw/logs/arete.log"; mkdir -p "$QA/raw/logs" "$OUTD"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

# 1. stage
while [ "$(systemctl --user show arete-dl -p ActiveState --value 2>/dev/null)" = active ]; do sleep 60; done
tail -1 "$SRC/download.log" | grep -q "ALL OK$" || { log "download did not end ALL OK: $(tail -1 "$SRC/download.log")"; exit 1; }
if [ ! -s "$OUT" ]; then
  log "converting to Q8_0"
  (cd /tmp && "$PY" "$LC/convert_hf_to_gguf.py" "$SRC" --outtype q8_0 --no-mtp --outfile "$OUT" > "$OUTD/convert.log" 2>&1) \
    || { log "convert failed: $(tail -2 "$OUTD/convert.log" | tr '\n' ' ')"; exit 1; }
fi
ARE_SHA=$(sha256sum "$OUT" | cut -d' ' -f1); log "Q8_0 $(stat -c %s "$OUT") bytes sha256 $ARE_SHA"
"$PY" -I "$HERE/tensor_map.py" "$LC/gguf-py" "$OUT" "$BASE_LOCAL" > "$HERE/tensor_map.txt" 2>&1; log "tensor map: $(sed -n 3p "$HERE/tensor_map.txt")"
if [ "$(ssh "$H" "sha256sum $ARE_F 2>/dev/null" | cut -d' ' -f1)" != "$ARE_SHA" ]; then
  scp -q "$OUT" "$H:AI/Models/qwopus/" || { log "scp failed"; exit 1; }
fi
for spec in "$ARE_F|$ARE_SHA" "$BASE_F|$BASE_SHA"; do
  IFS='|' read -r f want <<< "$spec"
  got=$(ssh "$H" "sha256sum $f" | cut -d' ' -f1); [ "$got" = "$want" ] || { log "HASH MISMATCH $f: $got"; exit 1; }
done
log "hashes verified on .194"
$PY -c 'import json,sys; h=json.loads(open(sys.argv[1]).readline()); open(sys.argv[2],"w").write(json.dumps(h["variant_ids"])); open(sys.argv[3],"w").write(h["render_tail"])' \
  "$QA/raw/main_C.A.jsonl" "$QA/raw/logs/ar_expect_variants.json" "$QA/raw/logs/ar_expect_tail.txt"

# 2. servers
ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "a llama-server is already running on .194 -- aborting"; exit 1; }
start() { ssh "$H" "CUDA_VISIBLE_DEVICES=$3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $2 $FLAGS --port $4 > ~/ar_$1.log 2>&1 < /dev/null &"; }
verify() {
  local i up=0
  for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$3/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "$1: not healthy after 600 s: $(ssh "$H" "tail -2 ~/ar_$1.log")"; return 1; }
  local mp; mp=$(curl -s -m 5 "http://$H:$3/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$2")" ] || { log "$1: WRONG SERVER answered: $mp"; return 1; }
  ssh "$H" "grep -q 'K (f16).*V (f16)' ~/ar_$1.log" || { log "$1: f16 KV line not found"; return 1; }
  log "$1: verified -- serving $(basename "$mp") on :$3"
}
start ARE "$ARE_F" 0,1 8190; start C.R2 "$BASE_F" 2,3 8191
verify ARE "$ARE_F" 8190 && verify C.R2 "$BASE_F" 8191 || { ssh "$H" 'pkill -x llama-server'; exit 1; }
ga=$($PY "$HERE/../ds41-h2h/prompt_gate.py" "http://$H:8190"); gb=$($PY "$HERE/../ds41-h2h/prompt_gate.py" "http://$H:8191")
log "prompt gate ARE $ga | C.R2 $gb"
[ -n "$ga" ] && [ "$ga" = "$gb" ] || { log "PROMPTS DIFFER between the arms -- aborting"; ssh "$H" 'pkill -x llama-server'; exit 1; }
log "GPUs: $(ssh "$H" 'nvidia-smi --query-gpu=index,power.limit,clocks.applications.graphics,memory.used --format=csv,noheader' | tr '\n' ';')"

# 3. run
run() {     # run ARM FILE GPUS PORT SHA
  local tail; tail=$(cat "$QA/raw/logs/ar_expect_tail.txt"; printf x); tail=${tail%x}   # $(cat) would strip "\n\n"
  local meta; meta=$($PY -c 'import json,sys; print(json.dumps(dict(zip(["arm","model","sha256","commit","flags","env","host"], sys.argv[1:]))))' \
    "$1" "$2" "$5" 0b2789f23f5ac10ed9a99aeb40ed10d3ba1c0163 "$FLAGS --port $4" "CUDA_VISIBLE_DEVICES=$3 GGML_CUDA_ALLREDUCE=internal" ".194")
  $PY "$QA/run_main.py" --url "http://$H:$4" --arm "$1" --meta "$meta" --usage \
    --expect-variants "$(cat "$QA/raw/logs/ar_expect_variants.json")" --expect-render-tail "$tail" > "$QA/raw/logs/ar_run_$1.log" 2>&1
  log "$1: run_main exit $? ($(( $(wc -l < "$QA/raw/main_$1.jsonl") - 1 )) rows)"
}
log "running both lanes"
run ARE "$ARE_F" 0,1 8190 "$ARE_SHA" & run C.R2 "$BASE_F" 2,3 8191 "$BASE_SHA" & wait
ssh "$H" 'pkill -x llama-server; for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done'
log "== done; powering .194 off"
"$ROOT/tools/s194.sh" off >> "$LOG" 2>&1
