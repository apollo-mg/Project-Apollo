#!/usr/bin/env bash
# Q6_K arm of PREREG_OVERTHINK_INJECTION.md, chained behind the nex-mini-ab three-way.
#
# Waits for the three-way on .194 to finish, starts a Q6_K server on the now-idle GPUs 0,1, then
# drives the same three arms against it. Nothing is launched while the three-way is still running:
# that run measures throughput, and adding load mid-arm would be an unregistered change to it.
#
# Everything is resumable — overthink_run.sh skips (arm, rep, item) cells already recorded — so a
# kill costs nothing but time.
set -u
cd "$(dirname "$0")"
N=10.0.0.194
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 $N"
MODEL=/home/mark/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
BIN=/home/mark/buun-llama-cpp/build_sm60_head/bin/llama-server
PORT=8095
OUTDIR=overthink_q6k
mkdir -p "$OUTDIR"
log () { echo "$(date '+%F %T') $*" | tee -a "$OUTDIR/chain.log"; }

log "waiting for the three-way to finish (polling every 3 min)"
while :; do
  n=$($SSH 'ls ~/hep/nex3_results_*.json 2>/dev/null | wc -l' 2>/dev/null || echo 0)
  a=$($SSH 'grep -c -E "ABORT|never ready" ~/hep/out/nex3/driver.log 2>/dev/null || echo 0' 2>/dev/null || echo 0)
  [ "${n:-0}" -ge 4 ] && { log "three-way COMPLETE ($n/4 result files)"; break; }
  [ "${a:-0}" -gt 0 ] && { log "three-way ABORTED ($a abort lines) — proceeding anyway, GPUs are free"; break; }
  sleep 180
done

# Belt and braces: do not start while any llama-server still holds GPUs 2,3.
for _ in $(seq 1 40); do
  busy=$($SSH 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | awk "\$1>1000{c++} END{print c+0}"' 2>/dev/null || echo 9)
  [ "${busy:-9}" -eq 0 ] && break
  log "  $busy GPU(s) still hold memory; waiting"
  sleep 60
done

log "starting Q6_K server on GPUs 0,1 (tensor split, f16 KV, ALLREDUCE=internal)"
$SSH "pgrep -x llama-server >/dev/null && echo 'WARNING: a llama-server is already running' ; \
  CUDA_VISIBLE_DEVICES=0,1 GGML_CUDA_ALLREDUCE=internal nohup setsid $BIN \
  -m '$MODEL' -ngl 99 -c 16384 -np 1 -fa on --kv-unified -ctk f16 -ctv f16 \
  -sm tensor --jinja --host 0.0.0.0 --port $PORT > ~/hep/out/overthink_q6k_server.log 2>&1 &" \
  >> "$OUTDIR/chain.log" 2>&1

# Readiness = a real completion. A 200 on /health is not proof (readiness-probes-lie).
HOST="http://$N:$PORT"
ready=0
for i in $(seq 1 120); do
  if curl -s -m 8 "$HOST/v1/chat/completions" -H 'Content-Type: application/json' \
       -d '{"messages":[{"role":"user","content":"Say READY"}],"max_tokens":4}' 2>/dev/null | grep -q '"content"'; then
    ready=1; log "server answered a real completion after ~$((i*5))s"; break
  fi
  sleep 5
done
[ $ready -eq 1 ] || { log "ABORT: server never produced a completion"; $SSH "tail -20 ~/hep/out/overthink_q6k_server.log" | tee -a "$OUTDIR/chain.log"; exit 1; }

log "running the three arms (resumable; this is the long part)"
HOST="$HOST" OUT="$OUTDIR" ./overthink_run.sh 999999 >> "$OUTDIR/chain.log" 2>&1
rc=$?
log "arms finished rc=$rc — rows: $(cat $OUTDIR/arm*_rep*.jsonl 2>/dev/null | wc -l)/144"
log "stopping the Q6_K server"
$SSH "pkill -x llama-server" >/dev/null 2>&1
log "CHAIN_DONE"
