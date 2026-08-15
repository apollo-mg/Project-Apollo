#!/usr/bin/env bash
set -u
B=/home/mark/moe-cache-test/src/build-hip/bin
M=/mnt/TG_2TB/AI/Models/qwen35
S=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
launch() {
    pkill -x llama-server 2>/dev/null; sleep 3
    LD_LIBRARY_PATH=$B "$B/llama-server" -m "$M/mtp-Q8_0.gguf" \
        -ngl 99 -c 8192 --jinja --host 127.0.0.1 --port 8082 "$@" \
        > "$S/srv_lossless.log" 2>&1 &
    for i in $(seq 1 180); do
        curl -sf http://127.0.0.1:8082/health >/dev/null 2>&1 && return 0
        pgrep -x llama-server >/dev/null || { echo "SERVER DIED"; tail -20 "$S/srv_lossless.log"; return 1; }
        sleep 1
    done; echo TIMEOUT; return 1; }
run(){ tag=$1; shift; echo "### $tag"; launch "$@" || return 1; $PY "$S/lossless_test.py" "${tag}_txt" 4; echo; }
run off
run mtp_n3 --spec-type draft-mtp --spec-draft-n-max 3
run dfl_n3 -md "$M/dflash-Q8_0.gguf" --spec-type draft-dflash -ngld 99 --spec-draft-n-max 3
pkill -x llama-server 2>/dev/null
echo "### LOSSLESS TEST DONE"
