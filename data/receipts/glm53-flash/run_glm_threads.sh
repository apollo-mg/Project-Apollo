#!/usr/bin/env bash
# PREREG_GLM_THREADS.md, from the desktop against .194: -t 20, 10, 30, 40, 20 with --numa distribute (mmap).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"; BIN='~/llama.cpp-upstream/build_sm60/bin/llama-server'
M='~/AI/Models/glm53_gguf_iq3xxs/GLM-5.3-Flash-UD-IQ3_XXS-00001-of-00004.gguf'
COMMON="-c 16384 -np 1 -ctk f16 -ctv f16 -lv 4 --numa distribute --host 0.0.0.0 --port $PORT"
OUT="$HERE/raw_threads"; mkdir -p "$OUT"; LOG="$OUT/run.log"; ROWS="$OUT/rows.jsonl"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
R() { timeout "${2:-60}" ssh -n -o BatchMode=yes "$H" "$1"; }
stop_server() { R 'pkill -x llama-server; for i in $(seq 1 90); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' 120 || { log "server survived pkill"; exit 1; }; }
trap stop_server EXIT
log "== glm-threads start; cfg: $(R 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" " "')"
for arm in t20a t10 t30 t40 t20b; do
  n=${arm#t}; n=${n%[ab]}
  [ "$(grep -c "\"arm\": \"$arm\"" "$ROWS" 2>/dev/null)" -ge 6 ] && { log "$arm done, skipped"; continue; }
  grep -q "\"arm\": \"$arm\"" "$ROWS" 2>/dev/null && { log "$arm partial -- refusing to mix"; exit 1; }
  stop_server; t0=$(date +%s)
  R "CUDA_VISIBLE_DEVICES=0,1,2,3 setsid nohup $BIN -m $M $COMMON -t $n > ~/glmthr_$arm.log 2>&1 < /dev/null & echo started" 20 >/dev/null
  up=0; for i in $(seq 1 180); do sleep 5
    R 'pgrep -x llama-server >/dev/null' || { log "$arm: server died: $(R "grep -i -E 'error|fail' ~/glmthr_$arm.log | tail -2")"; break; }
    curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "$arm: no server"; continue; }
  log "$arm: up in $(( $(date +%s) - t0 )) s; $(R "grep -o 'n_threads = [0-9]*[^|]*' ~/glmthr_$arm.log | head -1"); VRAM $(R 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr "\n" " "')"
  $PY "$HERE/glm_probe.py" "$URL" "$arm" "$ROWS" >> "$LOG" 2>&1 || log "$arm: probe failed"
  log "$arm: tps $(grep "\"arm\": \"$arm\"" "$ROWS" | $PY -c 'import json,sys; print([(json.loads(l)["pass"], round(json.loads(l)["tps"] or 0,2)) for l in sys.stdin])')"
done
stop_server; scp -q "$H:glmthr_*.log" "$OUT/" 2>/dev/null
R 'sudo systemctl restart p100-efficiency' >/dev/null 2>&1
log "== glm-threads done"
