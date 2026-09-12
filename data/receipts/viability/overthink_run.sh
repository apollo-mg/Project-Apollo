#!/usr/bin/env bash
# PREREG_OVERTHINK_INJECTION.md — three arms interleaved per (rep, item), resumable at item
# granularity. Both reasoning_budget fields are per-request, so one server serves all three arms.
#
# Resume: an (arm, rep, item) already present in its arm's jsonl is skipped, so the script can be
# re-run until it prints ALL_DONE. Stops launching new items once MAX seconds have elapsed, which
# keeps each invocation inside a foreground call.
#
# Usage: overthink_run.sh [MAX_SECONDS]   (default 540)
set -u
cd "$(dirname "$0")"
HOST=${HOST:-http://127.0.0.1:8094}
OUT=${OUT:-overthink}
MAX=${1:-540}
T0=$(date +%s)
mkdir -p "$OUT"

MSG='Are you overthinking this? Check: have you FOUND this, or are you building it? If the premise is false or the fact does not exist, answer UNKNOWN — that is a correct answer, not a failure. If you genuinely cannot resolve it either way, answer ADVISOR and then state, in one or two sentences, exactly what is blocking you and what you would ask an advisor. ADVISOR without that explanation is a failure, and ADVISOR leaves the task INCOMPLETE either way. Remember the meta goal. Speed ≠ goodness.'
BARE='Your thinking budget is exhausted. Answer now.'

ITEMS="CAL-A1 CAL-A2 CAL-A3 CAL-A4 CAL-A5 CAL-A6 CAL-A7 CAL-A8 CAL-U1 CAL-U2 CAL-U3 CAL-U4 CAL-U5 CAL-U6 CAL-U7 CAL-U8"

done_already () {    # arm rep item  -> 0 if that row exists
  local f="$OUT/arm${1}_rep${2}.jsonl"
  [ -s "$f" ] || return 1
  python3 - "$f" "$3" <<'PY'
import json, sys
want = sys.argv[2]
for line in open(sys.argv[1]):
    try:
        if json.loads(line).get("id") == want:
            raise SystemExit(0)
    except json.JSONDecodeError:
        pass
raise SystemExit(1)
PY
}

run_one () {         # arm rep item seed
  local arm=$1 rep=$2 item=$3 seed=$4
  local args=(--host "$HOST" --tier cal --sampling card --seed "$seed" --effort xhigh
              --only "$item" --arm "$arm" --jsonl "$OUT/arm${arm}_rep${rep}.jsonl")
  case "$arm" in
    A) : ;;                                             # unrestricted, no message
    B) args+=(--budget 220 --budget-message "$BARE") ;;
    C) args+=(--budget 220 --budget-message "$MSG") ;;
  esac
  python3 run_fixture_structfix.py "${args[@]}" > "$OUT/last_${arm}_${rep}_${item}.log" 2>&1
}

for rep in 1 2 3; do
  seed=$((1000 + rep))
  i=0
  for item in $ITEMS; do
    i=$((i + 1))
    # rotate arm order per (rep, item) so no arm owns a time slot
    case $(( (i + rep) % 3 )) in
      0) order="A B C" ;;
      1) order="B C A" ;;
      2) order="C A B" ;;
    esac
    for arm in $order; do
      done_already "$arm" "$rep" "$item" && continue
      if [ $(( $(date +%s) - T0 )) -ge "$MAX" ]; then
        echo "chunk budget reached; re-run to resume"; exit 3
      fi
      printf '%s rep%s %-8s arm %s ... ' "$(date +%T)" "$rep" "$item" "$arm"
      if run_one "$arm" "$rep" "$item" "$seed"; then
        python3 - "$OUT/arm${arm}_rep${rep}.jsonl" "$item" <<'PY'
import json, sys
for line in open(sys.argv[1]):
    try: r = json.loads(line)
    except json.JSONDecodeError: continue
    if r.get("id") == sys.argv[2]:
        print(f"{r.get('status'):14s} got={str(r.get('got'))[:28]:28s} think={len(r.get('reasoning') or ''):6d}")
PY
      else
        echo "FAILED (see $OUT/last_${arm}_${rep}_${item}.log)"
      fi
    done
  done
done
echo ALL_DONE
