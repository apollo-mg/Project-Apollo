#!/usr/bin/env bash
# PREREG_GLM_NUMA.md, from the desktop against .194. Arms M, B1, D, I, B2; page cache dropped before each.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"; BIN='~/llama.cpp-upstream/build_sm60/bin/llama-server'
M='~/AI/Models/glm53_gguf_iq3xxs/GLM-5.3-Flash-UD-IQ3_XXS-00001-of-00004.gguf'
COMMON="-c 16384 -np 1 -ctk f16 -ctv f16 -lv 4 --host 0.0.0.0 --port $PORT"
declare -A PRE=([M]="" [B1]="" [D]="" [I]="numactl --interleave=all" [B2]="")
declare -A EXTRA=([M]="" [B1]="--no-mmap" [D]="--no-mmap --numa distribute" [I]="--no-mmap --numa numactl" [B2]="--no-mmap")
OUT="$HERE/raw_numa"; mkdir -p "$OUT"; LOG="$OUT/run.log"; ROWS="$OUT/rows.jsonl"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
R() { timeout "${2:-60}" ssh -n -o BatchMode=yes "$H" "$1"; }
stop_server() { R 'pkill -x llama-server; for i in $(seq 1 90); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' 120 || { log "server survived pkill"; exit 1; }; }
trap stop_server EXIT
log "== glm-numa start; cfg: $(R 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" " "')"
for arm in M B1 D I B2; do
  [ "$(grep -c "\"arm\": \"$arm\"" "$ROWS" 2>/dev/null)" -ge 6 ] && { log "$arm done, skipped"; continue; }
  grep -q "\"arm\": \"$arm\"" "$ROWS" 2>/dev/null && { log "$arm partial -- refusing to mix"; exit 1; }
  stop_server
  R "sudo -n sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'" 120 || { log "drop_caches failed"; exit 1; }
  t0=$(date +%s)
  R "CUDA_VISIBLE_DEVICES=0,1,2,3 setsid nohup ${PRE[$arm]} $BIN -m $M $COMMON ${EXTRA[$arm]} > ~/glmnuma_$arm.log 2>&1 < /dev/null & echo started" 20 >/dev/null
  up=0; for i in $(seq 1 180); do sleep 5
    R 'pgrep -x llama-server >/dev/null' || { log "$arm: server died: $(R "grep -i -E 'error|fail|out of memory' ~/glmnuma_$arm.log | tail -2")"; break; }
    curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "$arm: no server"; continue; }
  load_s=$(( $(date +%s) - t0 ))
  pid=$(R 'pgrep -x llama-server')
  R "numastat -p $pid | tail -2; echo; awk '{for(i=1;i<=NF;i++) if(\$i ~ /^N[0-9]+=/){split(\$i,a,\"=\"); s[a[1]]+=a[2]}} END {for(k in s) printf \"%s=%d \", k, s[k]; print \"\"}' /proc/$pid/numa_maps" > "$OUT/numa_$arm.txt"
  log "$arm: up in ${load_s} s; pid $pid; $(R "grep -o 'n_threads = [0-9]*' ~/glmnuma_$arm.log | head -1"); VRAM $(R 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr "\n" " "'); numa_maps pages: $(tail -1 "$OUT/numa_$arm.txt")"
  $PY "$HERE/glm_probe.py" "$URL" "$arm" "$ROWS" >> "$LOG" 2>&1 || log "$arm: probe failed"
  log "$arm: tps $(grep "\"arm\": \"$arm\"" "$ROWS" | $PY -c 'import json,sys; print([(json.loads(l)["pass"], round(json.loads(l)["tps"] or 0,2)) for l in sys.stdin])')"
done
stop_server; scp -q "$H:glmnuma_*.log" "$OUT/" 2>/dev/null
R 'sudo systemctl restart p100-efficiency' >/dev/null 2>&1
log "== glm-numa done"
