#!/usr/bin/env bash
# PREREG_KMIC_TRUST_73 on .73: ./run_det73.sh [ARM...]  (default: DS KSa KGa KNa KN0 KSb KGb KNb)
# Precondition: wake proxy stopped, no llama-server running. Each arm: start server detached (PID recorded),
# run detbench.py, stop the server by its recorded PID.
set -u
W=~/kdtrust; mkdir -p $W; cd $W; L=$W/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
echo $$ > /tmp/apollo-busy.kdtrust; trap 'rm -f /tmp/apollo-busy.kdtrust' EXIT
MODEL='/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf'; MMPROJ='/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf'
BIN_D=/mnt/HDD/buun-510cb-nohost/build_sm60/bin/llama-server; BIN_K=/mnt/HDD/kmic-p100/src/build-opt/bin/llama-server
NET=(--host 127.0.0.1 --port 8087)
DS=(-m "$MODEL" --mmproj "$MMPROJ" -ngl 99 -c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 2 -fit off
    -sm tensor -fa on --spec-type draft-mtp --draft-max 3 --jinja --kv-unified
    --chat-template-kwargs '{"reasoning_effort":"medium"}' --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0
    --presence-penalty 0.0)
KBASE=(-m "$MODEL" -ngl 99 -sm tensor -fa 1 -ctk q4_0 -ctv q4_0 -c 262144 -b 32768 -ub 2048 -np 1)
KSPEC=(--spec-type draft-mtp --spec-draft-n-max 4 --spec-draft-p-min 0.2 -ngld 99 -ubd 64 -ctkd q4_0 -ctvd q4_0)
KTAIL=(--jinja --temp 1.0 --top-k 20 --top-p 0.95 --min-p 0.0 --mmproj "$MMPROJ")
for ARM in ${*:-DS KSa KGa KNa KN0 KSb KGb KNb}; do
  case $ARM in
    DS)      CMD=("$BIN_D" "${DS[@]}");;
    KSa|KSb) CMD=(env GGML_CUDA_GRAPHS_PRE_VOLTA=3 LLAMA_SPEC_SAMPLE_TEMP=1.0 LLAMA_SPEC_DRAFT_TOPK=20 "$BIN_K" "${KBASE[@]}" "${KSPEC[@]}" "${KTAIL[@]}");;
    KGa|KGb) CMD=(env GGML_CUDA_GRAPHS_PRE_VOLTA=3 "$BIN_K" "${KBASE[@]}" "${KSPEC[@]}" "${KTAIL[@]}");;
    KNa|KNb) CMD=(env GGML_CUDA_GRAPHS_PRE_VOLTA=3 "$BIN_K" "${KBASE[@]}" "${KTAIL[@]}");;
    KN0)     CMD=("$BIN_K" "${KBASE[@]}" "${KTAIL[@]}");;
    *) log "unknown arm $ARM"; exit 2;;
  esac
  pgrep -x llama-server >/dev/null && { log "ABORT $ARM: llama-server already running"; exit 1; }
  nvidia-smi --query-gpu=timestamp,index,clocks.applications.graphics,clocks.sm,power.limit,temperature.gpu --format=csv,noheader > $ARM.clocks
  printf '%q ' "${CMD[@]}" "${NET[@]}" > $ARM.cmd; echo >> $ARM.cmd
  setsid nohup "${CMD[@]}" "${NET[@]}" > $ARM.log 2>&1 < /dev/null & SP=$!; echo $SP > $ARM.pid
  log "$ARM started pid $SP"
  timeout 2400 python3 $W/detbench.py $ARM $W/$ARM.jsonl >> $L 2>&1; log "$ARM bench rc=$?"
  if kill -0 $SP 2>/dev/null; then A=alive; kill $SP; else A=DEAD; fi
  for i in $(seq 1 60); do kill -0 $SP 2>/dev/null || break; sleep 1; done
  kill -0 $SP 2>/dev/null && { kill -9 $SP; A="$A,SIGKILLED"; }
  log "$ARM end: $A abort_lines=$(grep -c -E 'GGML_ASSERT|ggml_abort|SIGABRT|Aborted|out of memory' $ARM.log)"
done
log DET_DONE
