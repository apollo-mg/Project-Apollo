#!/bin/bash
# PREREG_CODER_PRUNE.md, runs ON .194 against the already-verified server on :8096. IKP then HumanEval+, as
# run_reapfn.sh does them (same flags). Writes ~/reapfn/out_coder/ARM/{ikp.jsonl,hep_*} and ARM.DONE when finished.
set -u
ARM=$1; W=~/reapfn; O=$W/out_coder/$ARM; mkdir -p "$O"; PORT=8096
( cd "$W/ikp" && python3 ikp_run.py --endpoint "http://127.0.0.1:$PORT" --label "$ARM" --out "$O/ikp.jsonl" \
    --tiers T1,T2,T3,T4 --max-tokens 64 --no-think --exclude-source researcher ) > "$O/ikp.log" 2>&1
echo "ikp exit $? rows $(wc -l < "$O/ikp.jsonl")" > "$O/progress.txt"
if ! ls "$O"/hep_*.json >/dev/null 2>&1; then
  ( cd "$W/humaneval-plus" && HEP_ENDPOINT="http://127.0.0.1:$PORT/v1/chat/completions" HEP_MODEL="$ARM" \
      HEP_TEMP=0 HEP_K=1 HEP_THINK=0 HEP_MAXTOK=4096 HEP_PREFIX="$O/hep" python3 hep_eval.py ) > "$O/hep.log" 2>&1
  echo "hep exit $?" >> "$O/progress.txt"
fi
touch "$W/out_coder/$ARM.DONE"
