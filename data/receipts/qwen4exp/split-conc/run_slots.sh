#!/usr/bin/env bash
# PREREG_NUMA_PREFILL.md Deviation 1: forced slot pairs, L0 config, C0 binding; cfg A = as is, cfg B = --kv-unified
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"; BIN='~/buun-0b278/build_sm60/bin/llama-server'
M='~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf'
FLAGS="-ngl 99 -fa on -fit off -ctk f16 -ctv f16 -lv 4 --host 0.0.0.0 --port $PORT -sm layer -ts 1,1,1,0.6 -c 16384 -np 4"
OUT="$HERE/raw_numa"; LOG="$OUT/run.log"; ROWS="$OUT/slot_rows.jsonl"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
R() { timeout "${2:-60}" ssh -n -o BatchMode=yes "$H" "$1"; }
stop_server() { R 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' 90; }
trap stop_server EXIT
for cfg in A B; do
  extra=""; [ $cfg = B ] && extra="--kv-unified"
  stop_server
  R "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal setsid nohup numactl --cpunodebind=0 --preferred=0 $BIN -m $M $FLAGS $extra > ~/slots_$cfg.log 2>&1 < /dev/null & echo started" 20 >/dev/null
  up=0; for i in $(seq 1 120); do sleep 5
    R 'pgrep -x llama-server >/dev/null' || { log "slots $cfg: server died"; exit 1; }
    R "grep -q 'model loaded' ~/slots_$cfg.log" && curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "slots $cfg: not healthy"; exit 1; }
  R "grep -q 'offloaded 49/49 layers to GPU' ~/slots_$cfg.log" || { log "slots $cfg: not 49/49"; exit 1; }
  log "slots $cfg: verified; $(R "grep -o \"kv_unified = '[a-z]*'\" ~/slots_$cfg.log | head -1")"
  $PY "$HERE/slot_probe.py" "$URL" "$cfg" "$ROWS" >> "$LOG" 2>&1 || { log "slots $cfg: probe failed"; }
done
stop_server; scp -q "$H:slots_*.log" "$OUT/" 2>/dev/null
log "== slots done"
