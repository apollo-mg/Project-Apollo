#!/usr/bin/env bash
# Runs ON .194. PREREG_MARKER_PENALTY.md. One tester: ./marker_run.sh HOST OUTDIR   (resumable per (arm, rep, item))
# Adapted from viability/overthink_run.sh: same items, seeds, effort, sampling and arm rotation; arms differ by logit_bias only.
set -u
cd "$(dirname "$0")"
HOST=$1; OUT=$2
mkdir -p "$OUT"
ITEMS=${ITEMS:-"CAL-A1 CAL-A2 CAL-A3 CAL-A4 CAL-A5 CAL-A6 CAL-A7 CAL-A8 CAL-U1 CAL-U2 CAL-U3 CAL-U4 CAL-U5 CAL-U6 CAL-U7 CAL-U8"}   # Bonsai run splits items across testers

done_already () {    # arm rep item -> 0 if that row exists
  local f="$OUT/arm${1}_rep${2}.jsonl"
  [ -s "$f" ] || return 1
  python3 -c "import json,sys
for l in open(sys.argv[1]):
    try:
        if json.loads(l).get('id') == sys.argv[2]: sys.exit(0)
    except json.JSONDecodeError: pass
sys.exit(1)" "$f" "$3"
}

run_one () {         # arm rep item seed
  local arm=$1 rep=$2 item=$3 seed=$4
  local args=(--host "$HOST" --tier cal --sampling card --seed "$seed" --effort xhigh
              --only "$item" --arm "$arm" --jsonl "$OUT/arm${arm}_rep${rep}.jsonl")
  case "$arm" in
    A) : ;;
    B) args+=(--logit-bias-file bias_l2.json) ;;
    C) args+=(--logit-bias-file bias_l4.json) ;;
  esac
  python3 run_fixture_structfix.py "${args[@]}" > "$OUT/last_${arm}_${rep}_${item}.log" 2>&1
}

for rep in 1 2 3; do
  seed=$((1000 + rep)); i=0
  for item in $ITEMS; do
    i=$((i + 1))
    case $(( (i + rep) % 3 )) in 0) order="A B C" ;; 1) order="B C A" ;; 2) order="C A B" ;; esac
    for arm in $order; do
      done_already "$arm" "$rep" "$item" && continue
      printf '%s rep%s %-8s arm %s ... ' "$(date +%T)" "$rep" "$item" "$arm"
      if run_one "$arm" "$rep" "$item" "$seed"; then
        python3 -c "import json,sys
for l in open(sys.argv[1]):
    r = json.loads(l)
    if r.get('id') == sys.argv[2]: print(f\"{r.get('status'):16s} finish={r.get('finish')} think={len(r.get('reasoning') or ''):6d}\")" "$OUT/arm${arm}_rep${rep}.jsonl" "$item"
      else
        echo "FAILED (see $OUT/last_${arm}_${rep}_${item}.log)"
      fi
    done
  done
done
echo ALL_DONE
