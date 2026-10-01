#!/usr/bin/env bash
# PREREG_SPLIT_CONC.md. Cells L0 L3 T0 T3, each on a fresh verified server on .194. Resumable per cell.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"
BIN='~/buun-0b278/build_sm60/bin/llama-server'
M='~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf'
PLE='~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00002-of-00003.gguf'
MTP='-md ~/AI/Models/flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3'
BASE="-ngl 99 -c 16384 -np 4 -fa on -fit off -ctk f16 -ctv f16 -lv 4 --host 0.0.0.0 --port $PORT"
declare -A EXTRA=([L0]="-sm layer -ts 1,1,1,0.6" [L3]="-sm layer -ts 1,1,1,0.6 $MTP" [T0]="-sm tensor" [T3]="-sm tensor $MTP")
OUT="$HERE/raw"; mkdir -p "$OUT"; LOG="$OUT/run.log"; ROWS="$OUT/rows.jsonl"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
R() { timeout "${2:-60}" ssh -n -o BatchMode=yes "$H" "$1"; }
stop_server() { R 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' 90 || { log "server survived pkill"; exit 1; }; }
trap stop_server EXIT
log "== split-conc start; $(R 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" " "')"
for C in L0 L3 T0 T3; do
  grep -q "\"cell\": \"$C\", \"pass\": 2, \"n\": 4" "$ROWS" 2>/dev/null && { log "$C done, skipped"; continue; }
  stop_server
  R "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal setsid nohup $BIN -m $M $BASE ${EXTRA[$C]} > ~/sc_$C.log 2>&1 < /dev/null & echo started" 20 >/dev/null
  up=0; for i in $(seq 1 120); do sleep 5
    R 'pgrep -x llama-server >/dev/null' || { log "$C: server died: $(R "grep -i -E 'error|fail|not implemented' ~/sc_$C.log | tail -2")"; break; }
    R "grep -q 'model loaded' ~/sc_$C.log" && curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "$C: no server -- cell invalid"; continue; }
  mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$M")" ] || { log "$C: WRONG SERVER $mp"; exit 1; }
  R "grep -q 'offloaded 49/49 layers to GPU' ~/sc_$C.log" || { log "$C: not 49/49"; continue; }
  R "cat $PLE > /dev/null" 300
  $PY "$HERE/conc_probe.py" "$URL" "$C" "$ROWS" gate >> "$LOG" 2>&1 || { log "$C: G0 FAIL -- cell invalid"; continue; }
  $PY "$HERE/conc_probe.py" "$URL" "$C" "$ROWS" ref >> "$OUT/refs.jsonl" 2>>"$LOG"
  log "$C: verified, PLE pre-read, G0 pass; VRAM $(R 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr "\n" " "')"
  $PY "$HERE/conc_probe.py" "$URL" "$C" "$ROWS" run >> "$LOG" 2>&1
  log "$C: done"
done
stop_server; R 'sudo systemctl restart p100-efficiency' >/dev/null 2>&1
log "== split-conc done"
