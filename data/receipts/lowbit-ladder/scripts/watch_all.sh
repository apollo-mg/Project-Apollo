#!/usr/bin/env bash
# One line per completed cell across BOTH batches; ends when the prism batch ends or the chain
# gives up. Explicit bash: the harness's inline shell is zsh, where `mapfile` silently yields an
# empty array -- that defect made an earlier monitor report nothing for 30 minutes.
R() { ssh -n -o BatchMode=yes -o ConnectTimeout=10 mark@10.0.0.73 "$1" 2>/dev/null; }
seen=0
while true; do
  rows=$(R 'grep -E "CELL .*(OK|NO_RESULT|MISSING)|BATCH_DONE|PRISM_BATCH_START|PRISM_BATCH_DONE|SKIPPING" ~/ladder/cells/batch.log 2>/dev/null')
  n=$(printf '%s' "$rows" | grep -c .); n=${n:-0}
  if [ "$n" -gt "$seen" ]; then printf '%s\n' "$rows" | tail -n +$((seen+1)); seen=$n; fi
  if printf '%s' "$rows" | grep -q "PRISM_BATCH_DONE"; then echo "LADDER COMPLETE (both batches)"; exit 0; fi
  # the chain owns the handoff; if it is gone and the prism batch never finished, say why
  if ! R 'kill -0 $(cat ~/ladder/chain.pid 2>/dev/null) 2>/dev/null'; then
    if printf '%s' "$rows" | grep -q "PRISM_BATCH_DONE"; then echo "LADDER COMPLETE"; else
      echo "CHAIN ENDED without PRISM_BATCH_DONE -- $(R 'tail -2 ~/ladder/chain.log 2>/dev/null')"; fi
    exit 0
  fi
  sleep 30
done
