#!/bin/bash
# PREREG_BEAM_EFFORT chain on .194: for each arm in the registered order, a fresh server, a smoke gate on the rendered
# "Reasoning effort: N" line, the M1 run, then the server is stopped by its recorded, verified PID.
# A server death gets one resume on a fresh server (run_main.py skips written ids). `touch $O/STOP` ends the chain
# before the next arm starts.
O=$HOME/bench/beam-effort-1017; CL=$O/client/quant-abstention
BIN=$HOME/llama.cpp-beam/build_sm60/bin/llama-server
META='{"model": "AtomicChat/Beam-1.0-501B-A23B-GGUF AD-IQ2_XXS (3 shards, 133,789,612,416 B, sha256-verified)", "build": "llama.cpp f74e2fa6a sm_60", "placement": "last 28 MoE layers routed experts on CPU, -ts 8,6,6,33, --no-op-offload, -c 24576", "host": ".194 4x P100 150 W 1063 MHz", "prereg": "PREREG_BEAM_EFFORT.md"}'
log() { echo "$* $(date '+%F %T')" >> $O/state.log; }
stop_server() {
  p=$(cat $O/server.pid 2>/dev/null)
  [ -n "$p" ] && [ "$(readlink /proc/$p/exe 2>/dev/null)" = "$BIN" ] && kill $p && tail --pid=$p -f /dev/null
  [ -f $O/server_K28.log ] && mv $O/server_K28.log "$O/server_$1.log"
}
start_server() {
  cd $O; setsid ./serve_effort.sh 28 8,6,6,33 > /dev/null 2>&1 < /dev/null & echo $! > $O/server.pid
  for i in $(seq 180); do
    grep -q -a "listening on" $O/server_K28.log 2>/dev/null && return 0
    kill -0 $(cat $O/server.pid) 2>/dev/null || return 1
    sleep 5
  done; return 1
}
echo $$ > $O/chain.pid
stop_server probe
for spec in BEAMMAX:max:512 BEAMLOW:low:32 BEAMHIGH:high:128 BEAMMED:medium:64; do
  ARM=${spec%%:*}; rest=${spec#*:}; EFF=${rest%%:*}; N=${rest#*:}
  [ -f $O/STOP ] && { log "STOP file present: $ARM and later arms not started"; break; }
  for attempt in 1 2; do
    start_server || { log "$ARM attempt $attempt: server did not come up"; stop_server ${ARM}_fail$attempt; continue; }
    if ! curl -s 127.0.0.1:8091/apply-template -H 'Content-Type: application/json' \
         -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Q\"}],\"chat_template_kwargs\":{\"reasoning_effort\":\"$EFF\"}}" \
         | grep -q "Reasoning effort: $N"; then
      log "$ARM SMOKE GATE FAILED (no 'Reasoning effort: $N'): arm not run"; stop_server ${ARM}_smokefail; break
    fi
    log "$ARM attempt $attempt start (effort $EFF = $N)"
    cd $CL; python3 -s run_main.py --url http://127.0.0.1:8091 --arm $ARM --template-kwargs "{\"reasoning_effort\": \"$EFF\"}" \
      --skip-slot --no-think-check --max-tokens 8192 --usage --timeout 3600 --meta "$META" >> $O/run_$ARM.log 2>&1
    rc=$?; rows=$(( $(cat raw/main_$ARM.jsonl 2>/dev/null | wc -l) - 1 ))
    log "$ARM attempt $attempt rc=$rc rows=$rows"
    stop_server ${ARM}_a$attempt
    [ "$rows" -ge 240 ] && break
  done
done
log EFFORT_CHAIN_DONE
