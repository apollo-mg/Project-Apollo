#!/usr/bin/env bash
# .73 wake-time A/B (2026-10-05): weight load under --load-mode dio vs the default mmap, daily flags otherwise.
# --resume is OFF so the store is never touched; port 8081 so the proxy never forwards into a test server.
# Order dio, mmap, dio: dio bypasses the page cache, so the mmap arm cannot warm it.
# Holds a busy lock on .73 for the duration; stops the daily server by its PID and leaves the proxy to restart it.
set -uo pipefail
H=10.0.0.73; HERE="$(cd "$(dirname "$0")" && pwd)"; OUT="$HERE/raw_wake_ab"; mkdir -p "$OUT"; LOG="$OUT/run.log"
BIN=/mnt/HDD/buun-510cb-nohost/build_sm60/bin/llama-server
MD='/mnt/models/AI_Models/Qwen 3.8'
FLAGS="-ngl 99 -c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 2 -fit off -sm tensor -fa on --spec-type draft-mtp --draft-max 3 --jinja --kv-unified --host 0.0.0.0 --port 8081"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
R() { timeout "${2:-60}" ssh -n -o BatchMode=yes "$H" "$1"; }
wait_gone() { R "for i in \$(seq 1 150); do kill -0 $1 2>/dev/null || exit 0; sleep 1; done; exit 1" 170; }

R "setsid nohup sleep 3600 >/dev/null 2>&1 < /dev/null & echo \$! > /tmp/apollo-busy.wakeab" || { log "lock failed"; exit 1; }
log "busy lock held (pid $(R 'cat /tmp/apollo-busy.wakeab'))"
P=$(R "pgrep -x llama-server"); n=$(printf '%s\n' "$P" | grep -c .)
if [ "$n" = 1 ]; then
  log "stopping daily server pid $P (it saves its slots on the way down)"; t0=$(date +%s)
  R "kill $P"; wait_gone "$P" && log "daily server exited after $(( $(date +%s) - t0 ))s" || { log "daily server did not exit"; exit 1; }
elif [ "$n" != 0 ]; then log "expected one llama-server, found: $P"; exit 1; fi

arm() {  # NAME LOADMODE
  local name=$1 lm=$2 t0 up=0
  log "$name: page cache holds $(R "fincore -b -n '$MD/Qwen3.8-27B-Q6_K.gguf' | awk '{print \$1}'") bytes of the model"
  t0=$(date +%s.%N)
  R "setsid nohup $BIN -m '$MD/Qwen3.8-27B-Q6_K.gguf' --mmproj '$MD/mmproj-F16.gguf' $FLAGS $lm > ~/wakeab_$name.log 2>&1 < /dev/null & echo \$! > ~/wakeab.pid" 20
  for i in $(seq 1 600); do
    curl -sf -m 2 "http://$H:8081/health" >/dev/null && { up=1; break; }
    R "kill -0 \$(cat ~/wakeab.pid) 2>/dev/null" 10 || break
    sleep 0.5
  done
  local el; el=$(awk -v a="$(date +%s.%N)" -v b="$t0" 'BEGIN{printf "%.1f", a-b}')
  [ $up = 1 ] && log "$name ($lm): /health OK after ${el}s" || log "$name ($lm): FAILED after ${el}s"
  local pid; pid=$(R "cat ~/wakeab.pid"); R "kill $pid"; wait_gone "$pid" || log "$name: test server did not exit"
  scp -q "$H:wakeab_$name.log" "$OUT/server_$name.log"
}
arm dio1 "-lm dio"
arm mmap "-lm mmap"
arm dio2 "-lm dio"

R 'kill $(cat /tmp/apollo-busy.wakeab) 2>/dev/null; rm -f /tmp/apollo-busy.wakeab'; log "busy lock released"
t0=$(date +%s); r=$(curl -s -m 400 -X POST localhost:8099/wake); log "proxy /wake after test: $r ($(( $(date +%s) - t0 ))s)"
log "done"
