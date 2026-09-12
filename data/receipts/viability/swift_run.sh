#!/usr/bin/env bash
# PREREG_SWIFT_BREVITY_TAX.md — Swift IQ3_XXS, unrestricted thinking, on the 9070.
# One arm only: the comparison is against the already-collected BASE arm A in overthink/.
# Resumable at item granularity; re-run until it prints ALL_DONE.
set -u
cd "$(dirname "$0")"
HOST=${HOST:-http://127.0.0.1:8096}
OUT=${OUT:-swift}
MAX=${1:-999999}
T0=$(date +%s)
mkdir -p "$OUT"
ITEMS="CAL-A1 CAL-A2 CAL-A3 CAL-A4 CAL-A5 CAL-A6 CAL-A7 CAL-A8 CAL-U1 CAL-U2 CAL-U3 CAL-U4 CAL-U5 CAL-U6 CAL-U7 CAL-U8"

done_already () {
  local f="$OUT/swift_rep${1}.jsonl"
  [ -s "$f" ] || return 1
  python3 - "$f" "$2" <<'PY'
import json, sys
for line in open(sys.argv[1]):
    try:
        if json.loads(line).get("id") == sys.argv[2]: raise SystemExit(0)
    except json.JSONDecodeError: pass
raise SystemExit(1)
PY
}

for rep in 1 2 3; do
  seed=$((1000 + rep))
  for item in $ITEMS; do
    done_already "$rep" "$item" && continue
    if [ $(( $(date +%s) - T0 )) -ge "$MAX" ]; then echo "budget reached; re-run to resume"; exit 3; fi
    printf '%s rep%s %-8s ... ' "$(date +%T)" "$rep" "$item"
    python3 run_fixture_structfix.py --host "$HOST" --tier cal --sampling card --seed "$seed" \
      --effort xhigh --only "$item" --arm SWIFT --jsonl "$OUT/swift_rep${rep}.jsonl" \
      > "$OUT/last_${rep}_${item}.log" 2>&1 \
      && python3 - "$OUT/swift_rep${rep}.jsonl" "$item" <<'PY' || echo "FAILED"
import json, sys
for line in open(sys.argv[1]):
    try: r = json.loads(line)
    except json.JSONDecodeError: continue
    if r.get("id") == sys.argv[2]:
        print(f"{r.get('status'):16s} got={str(r.get('got'))[:26]:26s} think={len(r.get('reasoning') or ''):6d}")
PY
  done
done
echo ALL_DONE
