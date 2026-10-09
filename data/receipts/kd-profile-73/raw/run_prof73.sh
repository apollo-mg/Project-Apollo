#!/usr/bin/env bash
# PREREG_KD_PROFILE_73: profile cells PD16 PK16 PDQ4 PKQ4 on .73. Precondition: wake proxy stopped, daily server down.
# ./run_prof73.sh [CELL...]   Each cell: nsys 2022.4.2 wraps llama-server, client_prof.py sends the requests,
# SIGINT the server by its exact process name, wait for nsys by its recorded PID, export SQLite.
set -u
W=~/kdprof; mkdir -p $W; cd $W; L=$W/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
echo $$ > /tmp/apollo-busy.kdprof; trap 'rm -f /tmp/apollo-busy.kdprof' EXIT
NB=~/tools/nsys-2022.4.2/opt/nvidia/nsight-systems/2022.4.2; N=$NB/target-linux-x64/nsys
M="/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf"
BIN_D=/mnt/HDD/buun-510cb-nohost/build_sm60/bin/llama-server
BIN_K=/mnt/HDD/kmic-p100/src/build-opt/bin/llama-server
BASE=(-m "$M" -ngl 99 -sm tensor -fa on -b 2048 -ub 2048 -np 1 -fit off --host 127.0.0.1 --port 8086)
for CELL in ${*:-PD16 PK16 PDQ4 PKQ4}; do
  case $CELL in
    PD16) BIN=$BIN_D; KV=(-ctk f16 -ctv f16 -c 8192); MODE=f16;;
    PK16) BIN=$BIN_K; KV=(-ctk f16 -ctv f16 -c 8192); MODE=f16;;
    PDQ4) BIN=$BIN_D; KV=(-ctk q4_0 -ctv q4_0 -c 34816); MODE=q4;;
    PKQ4) BIN=$BIN_K; KV=(-ctk q4_0 -ctv q4_0 -c 34816); MODE=q4;;
    *) log "unknown cell $CELL"; exit 2;;
  esac
  pgrep -x llama-server >/dev/null && { log "ABORT $CELL: llama-server already running"; exit 1; }
  nvidia-smi --query-gpu=timestamp,index,clocks.sm,clocks.applications.graphics,power.limit,memory.used --format=csv,noheader > $CELL.clocks
  echo "$BIN ${BASE[*]} ${KV[*]}" > $CELL.cmd
  $N profile --force-overwrite=true -o $W/$CELL --trace=cuda --sample=none --cpuctxsw=none "$BIN" "${BASE[@]}" "${KV[@]}" > $CELL.log 2>&1 < /dev/null & NP=$!; echo $NP > $CELL.nsyspid
  log "$CELL launched nsys pid $NP"
  timeout 3600 python3 $W/client_prof.py $CELL $MODE $W/$CELL.jsonl >> $L 2>&1; log "$CELL client rc=$?"
  SP=$(pgrep -x llama-server); [ -n "$SP" ] && kill -INT $SP
  for i in $(seq 1 600); do kill -0 $NP 2>/dev/null || break; sleep 1; done
  kill -0 $NP 2>/dev/null && { log "$CELL nsys still running after 600 s"; kill $NP; }
  [ -f $W/$CELL.nsys-rep ] || { [ -f $W/$CELL.qdstrm ] && $NB/host-linux-x64/QdstrmImporter -i $W/$CELL.qdstrm >> $CELL.log 2>&1; }
  $N export --type sqlite --force-overwrite true -o $W/$CELL.sqlite $W/$CELL.nsys-rep >> $CELL.log 2>&1; log "$CELL export rc=$? $(ls -la $W/$CELL.sqlite 2>&1 | awk '{print $5}')"
done
log PROF_DONE
