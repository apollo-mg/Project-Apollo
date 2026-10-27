#!/usr/bin/env bash
# PREREG_STRATA_9070_Q36.md chain. Launch with:
#   systemd-run --user --unit=strata-q36 --collect -p MemoryMax=26G -p ExecStopPost="systemctl --user start apollo-clef.service apollo-clef-monitor.service" bash chain_q36.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; OUT="$HERE/runs"; mkdir -p "$OUT"; LOG="$OUT/run.log"
P="$HERE/../../gemma4-9070-spec"; CODE="$P/canonical_code-v1.txt"; REASON="$P/canonical_reasoning-v1.txt"
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_upstream_f74e2fa/build_rocm/bin/llama-server
MODEL=/mnt/TG_2TB/AI/Models/Qwen3.6-35B-A3B-base-GGUF/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
fits() {   # does llama.cpp load with K CPU expert layers and answer a smoke request?
  "$BIN" -m "$MODEL" -ngl 99 -fa on -c 32768 -ctk f16 -ctv f16 -np 1 -t 8 -fit off --n-cpu-moe "$1" \
    --chat-template-kwargs '{"enable_thinking":false}' --host 127.0.0.1 --port 8095 > "$OUT/fit_$1.log" 2>&1 < /dev/null &
  local sp=$! ok=1
  for i in $(seq 1 300); do kill -0 $sp 2>/dev/null || break; curl -sf -m 2 http://127.0.0.1:8095/health | grep -q ok && { ok=0; break; }; sleep 1; done
  if [ $ok = 0 ]; then
    curl -s -m 120 http://127.0.0.1:8095/v1/chat/completions -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"What is 17*19? Answer briefly."}],"max_tokens":32,"temperature":0}' | grep -q '323' || ok=1
  fi
  kill $sp 2>/dev/null; for i in $(seq 1 60); do kill -0 $sp 2>/dev/null || break; sleep 1; done
  return $ok
}
med() { python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('tokSOut') or 0)" "$OUT/lmx_$1.json" 2>/dev/null || echo 0; }
log "chain start (MemoryMax 26G); Clef stopping"; systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
bash "$HERE/run_q36.sh" strata S_code_r1 "$CODE"
bash "$HERE/run_q36.sh" strata S_code_r2 "$CODE"
bash "$HERE/run_q36.sh" strata S_reason "$REASON"
KMIN=""; for K in 12 14 16 18 20 22 24 26 28 30 32; do if fits $K; then KMIN=$K; break; else log "llama ncmoe $K: does not fit"; fi; done
[ -n "$KMIN" ] || { log "ABORT: no ncmoe up to 32 fits"; exit 1; }
log "llama K_min = $KMIN"
best=$KMIN; bv=0
for K in $KMIN $((KMIN+2)) $((KMIN+4)); do
  bash "$HERE/run_q36.sh" llama L_code_k$K "$CODE" $K; v=$(med L_code_k$K)
  python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) > float(sys.argv[2]) else 1)" "$v" "$bv" && { best=$K; bv=$v; }
done
log "llama best ncmoe = $best ($bv tok/s on code-v1)"
bash "$HERE/run_q36.sh" llama L_best_code_r2 "$CODE" $best
bash "$HERE/run_q36.sh" llama L_best_reason "$REASON" $best
log "strata hit rates: $(grep -hioE 'decode expert[^0-9]*hit rate[^0-9]*[0-9.]+ ?%?' /mnt/TG_2TB/Projects/strata/strata-qwen36-ud-q4_k_xl-nomtp.log "$OUT"/server_S_*.log 2>/dev/null | tail -6 | tr '\n' ';')"
log "unit memory peak: $(cat /sys/fs/cgroup$(systemctl --user show -p ControlGroup --value strata-q36)/memory.peak 2>/dev/null)"
log "DONE"
