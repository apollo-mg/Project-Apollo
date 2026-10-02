#!/usr/bin/env bash
# PREREG_NUMA_PREFILL.md, driven from the desktop against .194. Setup (page cache interleaved once), Part N (7 starts),
# Part P (6 cells). Resumable per start/cell. Never matches process lists by pattern: PIDs via pgrep -x, kill by PID.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"
BIN='~/buun-0b278/build_sm60/bin/llama-server'
D='~/AI/Models/flashnext_q2'; M="$D/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf"
S23="$D/Qwen3.8-Flash-Next-UD-Q2_K_XL-00002-of-00003.gguf $D/Qwen3.8-Flash-Next-UD-Q2_K_XL-00003-of-00003.gguf"
COMMON="-ngl 99 -fa on -fit off -ctk f16 -ctv f16 -lv 4 --host 0.0.0.0 --port $PORT"
declare -A BIND=([U]="" [C0]="numactl --cpunodebind=0 --preferred=0" [C1]="numactl --cpunodebind=1 --preferred=1")
OUT="$HERE/raw_numa"; mkdir -p "$OUT"; LOG="$OUT/run.log"; NROWS="$OUT/n_rows.jsonl"; PROWS="$OUT/p_rows.jsonl"
TEXT="$OUT/wiki.test.raw"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
R() { timeout "${2:-60}" ssh -n -o BatchMode=yes "$H" "$1"; }
stop_server() { R 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' 90 || { log "server survived pkill"; exit 1; }; }
trap 'stop_server; R "test -s ~/numa_sampler.pid && kill \$(cat ~/numa_sampler.pid) 2>/dev/null; rm -f ~/numa_sampler.pid"' EXIT

start() {  # TAG BINDKEY EXTRA-FLAGS -> 0 when verified
  local tag=$1 key=$2 extra=$3
  stop_server
  R "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal setsid nohup ${BIND[$key]} $BIN -m $M $COMMON $extra > ~/numa_$tag.log 2>&1 < /dev/null & echo started" 20 >/dev/null
  local up=0
  for i in $(seq 1 120); do sleep 5
    R 'pgrep -x llama-server >/dev/null' || { log "$tag: server died: $(R "grep -i -E 'error|fail|out of memory' ~/numa_$tag.log | tail -2")"; return 1; }
    R "grep -q 'model loaded' ~/numa_$tag.log" && curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }
  done
  [ $up = 1 ] || { log "$tag: not healthy"; return 1; }
  local mp; mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$M")" ] || { log "$tag: WRONG MODEL $mp"; exit 1; }
  R "grep -q 'offloaded 49/49 layers to GPU' ~/numa_$tag.log" || { log "$tag: not 49/49"; return 1; }
  local pid; pid=$(R 'pgrep -x llama-server')
  R "cat /proc/$pid/status | grep -E '^Cpus_allowed_list'; numastat -p $pid | tail -3" > "$OUT/numastat_$tag.txt"
  log "$tag: verified ($key, pid $pid, $(head -1 "$OUT/numastat_$tag.txt" | tr -s ' \t' ' ')); VRAM $(R 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr "\n" " "'); $(R "grep -o 'pipeline parallelism enabled[^,]*' ~/numa_$tag.log | head -1")"
}
sampler_on() {  # TAG: running-thread CPU samples every 0.5 s (numa_sampler.sh on .194)
  R "setsid nohup sh ~/numa_sampler.sh \$(pgrep -x llama-server) ~/psr_$1.txt > /dev/null 2>&1 < /dev/null & echo \$! > ~/numa_sampler.pid" 20 >/dev/null
}
sampler_off() { R 'kill $(cat ~/numa_sampler.pid) 2>/dev/null; rm -f ~/numa_sampler.pid' 20; scp -q "$H:psr_$1.txt" "$OUT/" 2>/dev/null; }

log "== numa-prefill start; cfg: $(R 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr "\n" " "')"
# ---- setup: interleave the file pages once
if [ ! -s "$OUT/numastat_m_after.txt" ]; then
  stop_server
  R "numastat -m | grep -E 'MemFree|FilePages'" > "$OUT/numastat_m_before.txt"
  R "sudo -n sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'" 60 || { log "drop_caches failed"; exit 1; }
  t0=$(date +%s); R "numactl --interleave=all cat $S23 > /dev/null" 900
  R "numastat -m | grep -E 'MemFree|FilePages'" > "$OUT/numastat_m_after.txt"
  log "setup: caches dropped, shards 2+3 read interleaved in $(( $(date +%s) - t0 )) s; FilePages: $(grep FilePages "$OUT/numastat_m_after.txt" | tr -s ' ')"
fi
[ -s "$TEXT" ] || scp -q "$H:wikitext-2-raw/wiki.test.raw" "$TEXT"
scp -q "$HERE/numa_sampler.sh" "$H:numa_sampler.sh"

# ---- Part N
NFLAGS="-sm layer -ts 1,1,1,0.6 -c 16384 -np 4"
for tag in U1 C0a U2 C1a U3 C0b C1b; do
  case $tag in U*) key=U;; C0*) key=C0;; C1*) key=C1;; esac
  [ "$(grep -c "\"cell\": \"$tag\"" "$NROWS" 2>/dev/null)" -ge 12 ] && { log "$tag done, skipped"; continue; }
  grep -q "\"cell\": \"$tag\"" "$NROWS" 2>/dev/null && { log "$tag partial -- refusing to mix"; exit 1; }
  start "$tag" "$key" "$NFLAGS" || continue
  $PY "$HERE/conc_probe.py" "$URL" "$tag" "$NROWS" gate >> "$LOG" 2>&1 || { log "$tag: G0 FAIL"; continue; }
  for half in 1 2; do
    sampler_on "${tag}_$half"
    $PY "$HERE/conc_probe.py" "$URL" "$tag" "$NROWS" run >> "$LOG" 2>&1
    sampler_off "${tag}_$half"
  done
  log "$tag: done; 2-stream agg_tps: $(grep "\"cell\": \"$tag\"" "$NROWS" | $PY -c 'import json,sys; print([json.loads(l)["agg_tps"] for l in sys.stdin if json.loads(l)["n"]==2])')"
done

# ---- Part P (C0 for every cell)
for cell in L512 L2048 L4096 T512 T2048 T4096; do
  [ "$(grep -c "\"cell\": \"$cell\"" "$PROWS" 2>/dev/null)" -ge 6 ] && { log "$cell done, skipped"; continue; }
  grep -q "\"cell\": \"$cell\"" "$PROWS" 2>/dev/null && { log "$cell partial -- refusing to mix"; exit 1; }
  ub=${cell:1}; b=$(( ub > 2048 ? ub : 2048 ))
  case $cell in L*) sm="-sm layer -ts 1,1,1,0.6";; T*) sm="-sm tensor";; esac
  start "$cell" C0 "$sm -c 16384 -np 1 -b $b -ub $ub" || { log "$cell: no server (recorded as the cell's result)"; continue; }
  $PY "$HERE/conc_probe.py" "$URL" "$cell" /dev/null gate >> "$LOG" 2>&1 || { log "$cell: G0 FAIL"; continue; }
  sampler_on "$cell"
  $PY "$HERE/pf_probe.py" "$URL" "$cell" "$PROWS" "$TEXT" >> "$LOG" 2>&1
  sampler_off "$cell"
  log "$cell: done; pps: $(grep "\"cell\": \"$cell\"" "$PROWS" | $PY -c 'import json,sys; print([(json.loads(l)["n"], round(json.loads(l)["pps"] or 0,1)) for l in sys.stdin])')"
done
stop_server
scp -q "$H:numa_*.log" "$OUT/" 2>/dev/null
R 'sudo systemctl restart p100-efficiency' >/dev/null 2>&1
log "== numa-prefill done"
