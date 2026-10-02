#!/usr/bin/env bash
# PREREG_RECIPE.md, from the desktop against .194: setup (file pages interleaved once), servers R1 and R2.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"; BIN='~/buun-0b278/build_sm60/bin/llama-server'
D='~/AI/Models/flashnext_q2'; M="$D/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf"
S23="$D/Qwen3.8-Flash-Next-UD-Q2_K_XL-00002-of-00003.gguf $D/Qwen3.8-Flash-Next-UD-Q2_K_XL-00003-of-00003.gguf"
MTP='-md ~/AI/Models/flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3'
COMMON="-ngl 99 -fa on -fit off -ctk f16 -ctv f16 -lv 4 -c 16384 -ub 4096 -b 4096 --kv-unified --host 0.0.0.0 --port $PORT"
declare -A CFG=([R1]="-sm tensor -ts 1,1,1,0.75 $MTP -np 2" [R2]="-sm tensor -np 4" [R1b]="-sm tensor -ts 1,1,1,0.75 $MTP -np 2 -ub 2048 -b 2048" [R1c]="-sm tensor -ts 1,1,1,0.75 $MTP -np 2 -ub 1024 -b 1024")
SERVERS=${SERVERS:-"R1 R2"}
OUT="$HERE/raw_recipe"; mkdir -p "$OUT"; LOG="$OUT/run.log"; PROWS="$OUT/p_rows.jsonl"; NROWS="$OUT/n_rows.jsonl"
TEXT="$HERE/raw_numa/wiki.test.raw"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
R() { timeout "${2:-60}" ssh -n -o BatchMode=yes "$H" "$1"; }
stop_server() { R 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' 90 || { log "server survived pkill"; exit 1; }; }
trap stop_server EXIT
log "== recipe start; cfg: $(R 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" " "')"
if [ ! -s "$OUT/setup.done" ]; then
  stop_server; R "sudo -n sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'" 60 || { log "drop_caches failed"; exit 1; }
  t0=$(date +%s); R "numactl --interleave=all cat $S23 > /dev/null" 900
  log "setup: shards 2+3 interleaved in $(( $(date +%s) - t0 )) s; $(R "numastat -m | grep FilePages" | tr -s ' ')"; echo ok > "$OUT/setup.done"
fi
for s in $SERVERS; do
  grep -q "\"cell\": \"$s\"" "$PROWS" 2>/dev/null && { log "$s has rows -- skipped (move aside to rerun)"; continue; }
  stop_server
  R "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal setsid nohup numactl --cpunodebind=0 --preferred=0 $BIN -m $M $COMMON ${CFG[$s]} > ~/recipe_$s.log 2>&1 < /dev/null & echo started" 20 >/dev/null
  up=0; for i in $(seq 1 120); do sleep 5
    R 'pgrep -x llama-server >/dev/null' || { log "$s: server died (recorded as its result): $(R "grep -i -E 'error|fail|out of memory' ~/recipe_$s.log | tail -2")"; break; }
    R "grep -q 'model loaded' ~/recipe_$s.log" && curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "$s: no server"; continue; }
  R "grep -q 'offloaded 49/49 layers to GPU' ~/recipe_$s.log" || { log "$s: not 49/49"; continue; }
  log "$s: verified; $(R "grep -o \"kv_unified = '[a-z]*'\" ~/recipe_$s.log | head -1"); VRAM $(R 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr "\n" " "')"
  $PY "$HERE/conc_probe.py" "$URL" "$s" /dev/null gate >> "$LOG" 2>&1 || { log "$s: G0 FAIL"; continue; }
  $PY "$HERE/pf_probe.py" "$URL" "$s" "$PROWS" "$TEXT" >> "$LOG" 2>&1 || log "$s: prefill probe error"
  for half in 1 2; do $PY "$HERE/conc_probe.py" "$URL" "$s" "$NROWS" run >> "$LOG" 2>&1; done
  log "$s: done; pps $(grep "\"cell\": \"$s\"" "$PROWS" | $PY -c 'import json,sys; print([(json.loads(l)["n"], round(json.loads(l)["pps"] or 0,1)) for l in sys.stdin])'); n-stream agg $(grep "\"cell\": \"$s\"" "$NROWS" | $PY -c 'import json,sys; print([(json.loads(l)["n"], json.loads(l)["agg_tps"], json.loads(l)["fail"]) for l in sys.stdin])')"
done
stop_server; scp -q "$H:recipe_*.log" "$OUT/" 2>/dev/null
log "== recipe done"
