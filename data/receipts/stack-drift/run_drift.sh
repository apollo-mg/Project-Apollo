#!/bin/bash
# PREREG_STACK_DRIFT runner for ONE stack: run_drift.sh desk|n194|n73
# M1 Qwen3.5-9B twice (fresh server each), KLD against the CPU base (raw/kld_base.bin must exist), and on n194/n73 the
# 27B daily model once on two cards. The M1 driver always runs on the desktop against the stack's server.
set -u
STACK=$1
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/stack-drift; QA=$R/data/receipts/quant-abstention
PY=$R/venv_cachyos/bin/python3; S=$H/raw/state_drift_$STACK.log; log() { echo "$* $(date '+%F %T')" >> $S; }
COMMIT=33aeb17f8; FL="-c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0"
case $STACK in
  desk) HOST=local; IP=127.0.0.1; PORT=8095; BIN=$R/engines/rocm10/up_33aeb17f/build_rocm/bin
        Q35=/mnt/TG_2TB/AI/Models/sci-distill-gguf/Qwen3.5-9B-Q8_0.gguf; ENV1=""; GPU1="-ngl 99"; WD=$H/raw/desk ;;
  n194) HOST=mark@10.0.0.194; IP=10.0.0.194; PORT=8190; BIN=/home/mark/llama.cpp-33aeb17f/build_sm60/bin
        Q35=/home/mark/AI/Models/sci-distill/Qwen3.5-9B-Q8_0.gguf; Q27=/home/mark/AI/Models/qwopus/Qwen3.8-27B-Q8_0.gguf
        ENV1="CUDA_VISIBLE_DEVICES=0 GGML_CUDA_ALLREDUCE=internal"; GPU1="-ngl 99 -sm layer -fit off"; WD=/home/mark/drift ;;
  n73)  HOST=mark@10.0.0.73; IP=10.0.0.73; PORT=8190; BIN=/home/mark/llama.cpp-33aeb17f/build_sm60/bin
        Q35=/mnt/models/drift/Qwen3.5-9B-Q8_0.gguf; Q27=/mnt/HDD/kld/Qwen3.8-27B-Q8_0.gguf
        ENV1="CUDA_VISIBLE_DEVICES=0 GGML_CUDA_ALLREDUCE=internal"; GPU1="-ngl 99 -sm layer -fit off"; WD=/home/mark/drift ;;
  *) echo "usage: run_drift.sh desk|n194|n73"; exit 2 ;;
esac
rx() { if [ $HOST = local ]; then bash -c "$1"; else ssh -o BatchMode=yes $HOST "$1"; fi; }
rx "mkdir -p $WD"
# a busy lock on the P100 nodes (the wake proxy honours /tmp/apollo-busy.*); this runner's PID is not on the node, so the
# lock holds a long sleep that is killed at the end
[ $HOST != local ] && rx "setsid nohup sleep 86400 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/apollo-busy.drift"
log "start $STACK; binary $(rx "sha256sum $BIN/llama-server | cut -c1-16"); $(rx "nvidia-smi --query-gpu=driver_version,name --format=csv,noheader 2>/dev/null | head -1; pacman -Q hip-runtime-amd 2>/dev/null")"
serve() {  # serve TAG MODEL "ENV" "GPUFLAGS"
  rx "$3 setsid nohup $BIN/llama-server -m $2 $4 $FL --host 0.0.0.0 --port $PORT > $WD/server_$1.log 2>&1 < /dev/null & echo \$! > $WD/server.pid"
  for i in $(seq 240); do curl -s -m 3 $IP:$PORT/health 2>/dev/null | grep -q ok && return 0; sleep 2; done; return 1
}
stop() { rx "kill \$(cat $WD/server.pid) 2>/dev/null; sleep 3"; }
m1() {  # m1 ARM MODELDESC
  ( cd $QA && $PY run_main.py --url http://$IP:$PORT --arm $1 --max-tokens 1024 --usage \
      --meta "{\"model\": \"$2\", \"commit\": \"$COMMIT\", \"stack\": \"$STACK\", \"prereg\": \"PREREG_STACK_DRIFT.md\"}" > $H/raw/run_$1.log 2>&1 )
  log "$1 rc=$? rows=$(( $(wc -l < $QA/raw/main_$1.jsonl) - 1 ))"
}
U=$(echo $STACK | tr a-z A-Z)
for n in 1 2; do
  if serve DR_${U}_$n $Q35 "$ENV1" "$GPU1"; then m1 DR_${U}_$n "Qwen3.5-9B-Q8_0.gguf (f904644b)"; else log "DR_${U}_$n server failed"; fi
  stop
done
# KLD against the CPU base
[ $HOST != local ] && scp -q $H/raw/kld_base.bin $HOST:$WD/kld_base.bin
KB=$( [ $HOST = local ] && echo $H/raw/kld_base.bin || echo $WD/kld_base.bin )
rx "$ENV1 $BIN/llama-perplexity -m $Q35 --kl-divergence-base $KB --kl-divergence -c 512 --chunks 10 $GPU1 -ctk f16 -ctv f16 > $WD/kld_$STACK.log 2>&1"
log "KLD $STACK rc=$?"
[ $HOST != local ] && scp -q $HOST:$WD/kld_$STACK.log $H/raw/ && scp -q "$HOST:$WD/server_*.log" $H/raw/ 2>/dev/null
# the 27B daily model on two cards (P100 nodes only)
if [ $HOST != local ]; then
  if serve DR27_$U $Q27 "CUDA_VISIBLE_DEVICES=0,1 GGML_CUDA_ALLREDUCE=internal" "-ngl 99 -sm layer -fit off"; then
    m1 DR27_$U "Qwen3.8-27B-Q8_0.gguf (a680f44a)"; else log "DR27_$U server failed"; fi
  stop; scp -q "$HOST:$WD/server_DR27_*.log" $H/raw/ 2>/dev/null
  rx "kill \$(cat /tmp/apollo-busy.drift) 2>/dev/null; rm -f /tmp/apollo-busy.drift"
fi
log DRIFT_DONE
