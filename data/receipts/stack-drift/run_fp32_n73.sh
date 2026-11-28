#!/bin/bash
# PREREG_SM60_FP32 on .73: pause the wake proxy, stop the daily server, build 33aeb17f8 with the carve-out (build_engine.sh
# default), KLD unpatched (G1 replay) and patched against the CPU base, M1 9B on the patched build, then restore the proxy.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/stack-drift; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
S=$H/raw/state_fp32_n73.log; log() { echo "$* $(date '+%F %T')" >> $S; }
HOST=mark@10.0.0.73; IP=10.0.0.73; PORT=8190; WD='~/drift'; Q35=/mnt/models/drift/Qwen3.5-9B-Q8_0.gguf
OLD='~/llama.cpp-33aeb17f/build_sm60/bin'; NEW='~/llama.cpp-33aeb17f-fp32/build_sm60/bin'
ENV1="CUDA_VISIBLE_DEVICES=0 GGML_CUDA_ALLREDUCE=internal"; GPU1="-ngl 99 -sm layer -fit off"
FL="-c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0"
rx() { ssh -o BatchMode=yes $HOST "$1"; }
curl -s -m 120 -X POST 127.0.0.1:8099/wake > /dev/null; sleep 3
systemctl --user stop apollo-wake-proxy; log "wake proxy stopped"
rx "setsid nohup sleep 21600 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/apollo-busy.fp32"
P=$(rx 'pgrep -x llama-server'); [ -n "$P" ] && rx "kill $P"; log "daily server pids stopped: ${P:-none}"
for i in $(seq 60); do u=$(rx "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1"); [ "${u:-99999}" -lt 500 ] && break; sleep 5; done
log "VRAM before (max) ${u} MiB; clocks $(rx "nvidia-smi --query-gpu=clocks.sm,clocks.max.sm,power.limit --format=csv,noheader | tr '\n' ' '")"
rx "SRC=/mnt/HDD/llama.cpp-v0.7.0 bash -s -- sm60 33aeb17f8" < $R/data/scorecard/build_engine.sh > $H/raw/build_fp32_n73.log 2>&1
log "build: $(tail -1 $H/raw/build_fp32_n73.log)"
if tail -1 $H/raw/build_fp32_n73.log | grep -q "BUILD_OK.*+sm60-fp32-carveout"; then
  for T in OLD NEW; do
    B=$( [ $T = OLD ] && echo $OLD || echo $NEW )
    rx "$ENV1 $B/llama-perplexity -m $Q35 --kl-divergence-base $WD/kld_base.bin --kl-divergence -c 512 --chunks 10 $GPU1 -ctk f16 -ctv f16 > $WD/kld_fp32_$T.log 2>&1"
    log "KLD $T rc=$? $(rx "grep -E 'Mean    KLD|Same top p' $WD/kld_fp32_$T.log | tr '\n' ' '")"
    scp -q $HOST:drift/kld_fp32_$T.log $H/raw/
  done
  rx "$ENV1 setsid nohup $NEW/llama-server -m $Q35 $GPU1 $FL --host 0.0.0.0 --port $PORT > $WD/server_DR_N73F_1.log 2>&1 < /dev/null & echo \$! > $WD/server.pid"
  ok=0; for i in $(seq 240); do curl -s -m 3 $IP:$PORT/health | grep -q ok && { ok=1; break; }; sleep 2; done; log "M1 server healthy=$ok"
  if [ $ok = 1 ]; then
    ( cd $QA && $PY run_main.py --url http://$IP:$PORT --arm DR_N73F_1 --max-tokens 1024 --usage \
        --meta "{\"model\": \"Qwen3.5-9B-Q8_0.gguf (f904644b)\", \"commit\": \"33aeb17f8 +sm60-fp32-carveout\", \"stack\": \"n73\", \"prereg\": \"PREREG_SM60_FP32.md\"}" > $H/raw/run_DR_N73F_1.log 2>&1 )
    log "DR_N73F_1 rc=$? rows=$(( $(wc -l < $QA/raw/main_DR_N73F_1.jsonl) - 1 ))"
  fi
  rx "kill \$(cat $WD/server.pid) 2>/dev/null"; sleep 3; scp -q $HOST:drift/server_DR_N73F_1.log $H/raw/
else log "build did not report the patch; nothing run"; fi
rx "kill \$(cat /tmp/apollo-busy.fp32) 2>/dev/null; rm -f /tmp/apollo-busy.fp32"
systemctl --user start apollo-wake-proxy; log "wake proxy started; FP32_DONE"
