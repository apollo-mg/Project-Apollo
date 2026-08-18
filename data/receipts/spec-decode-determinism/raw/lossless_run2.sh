#!/usr/bin/env bash
# B1: re-run the speculation-losslessness test with cache_prompt swept BOTH ways.
#
# RESULT_SPECULATION_IS_NOT_BIT_EXACT (08-15) found 0/12 speculative runs matching the
# non-speculative reference, and is marked PROVISIONAL because it ran with cache_prompt at
# its default TRUE. Two other receipts cite it.
#
# Sweeping both settings separates the two explanations:
#   CACHE=1 reproduces the original -> confirms the machine still behaves as it did on 08-15
#   CACHE=0 is the actual test       -> if the arms converge, the finding was a caching artifact
set -u
B=/home/mark/moe-cache-test/src/build-hip/bin
M=/mnt/TG_2TB/AI/Models/qwen35
S=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
REPS=6
launch() {
    pkill -x llama-server 2>/dev/null; sleep 4
    LD_LIBRARY_PATH=$B "$B/llama-server" -m "$M/mtp-Q8_0.gguf" \
        -ngl 99 -c 8192 --jinja --host 127.0.0.1 --port 8082 "$@" \
        > "$S/srv_lossless2.log" 2>&1 &
    for i in $(seq 1 180); do
        curl -sf http://127.0.0.1:8082/health >/dev/null 2>&1 && return 0
        pgrep -x llama-server >/dev/null || { echo "  SERVER DIED"; tail -6 "$S/srv_lossless2.log"; return 1; }
        sleep 1
    done; echo "  TIMEOUT"; return 1; }
run(){ tag=$1; shift; echo "### $tag  (cache_prompt=$CACHE_PROMPT)"; launch "$@" || return 1
       CACHE_PROMPT=$CACHE_PROMPT $PY "$S/lossless_test2.py" "${tag}_c${CACHE_PROMPT}" $REPS; echo; }
for CACHE_PROMPT in 1 0; do
  export CACHE_PROMPT
  echo "############ cache_prompt=$CACHE_PROMPT ############"
  run off
  run mtp_n3 --spec-type draft-mtp --spec-draft-n-max 3
  run dfl_n3 -md "$M/dflash-Q8_0.gguf" --spec-type draft-dflash -ngld 99 --spec-draft-n-max 3
done
pkill -x llama-server 2>/dev/null
echo "### B1 DONE $(date -Is)"
