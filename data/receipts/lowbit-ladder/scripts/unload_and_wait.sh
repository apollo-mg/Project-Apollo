#!/usr/bin/env bash
# Stop the daily driver by EXACT PID (never a pattern) and wait for the VRAM to actually drain.
# "the kill returned" is not "the memory is free" -- launching the gate against a draining card
# produces an OOM that reads like a model defect. See readiness-probes-lie.
set -u
PID=41610
echo "before: $(timeout 10 nvidia-smi --query-gpu=index,memory.used --format=csv,noheader)"
if ! kill -0 "$PID" 2>/dev/null; then echo "PID $PID not alive; nothing to stop"; else
  # Re-confirm identity at signal time. A PID is not a stable name: if the server had restarted,
  # 41610 could belong to anything by now. Reading THIS pid's cmdline is not a process-list search.
  CMD=$(tr '\0' ' ' < /proc/$PID/cmdline)
  case "$CMD" in
    *llama-server*) echo "confirmed target: ${CMD:0:80}..." ;;
    *) echo "REFUSING: pid $PID is not llama-server, it is: $CMD"; exit 1 ;;
  esac
  kill -TERM "$PID"; echo "sent SIGTERM to $PID"
fi
for i in $(seq 1 60); do
  sleep 2
  USED=$(timeout 10 nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' ' ')
  HI=$(echo "$USED" | tr ' ' '\n' | grep -v '^$' | sort -rn | head -1)
  if [ "${HI:-99999}" -lt 500 ]; then
    echo "drained after $((i*2))s: $USED"
    kill -0 "$PID" 2>/dev/null && echo "WARN: pid $PID still alive despite free VRAM" || echo "pid $PID gone"
    exit 0
  fi
done
echo "TIMEOUT: VRAM did not drain below 500 MiB in 120s; last=$USED"
exit 1
