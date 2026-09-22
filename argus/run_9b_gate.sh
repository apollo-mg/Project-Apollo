#!/usr/bin/env bash
# 9B gate: 4 arms, sequential, RX 9070. See data/receipts/argus-9b/PREREG_9B_GATE.md
#
# ALL sampling pinned explicitly (AFM-42): MiMo's GGUF embeds
# general.sampling.temp 0.6 / top_k 20 / top_p 0.95 and Ornith's embeds nothing,
# so identical flags would otherwise sample at different temperatures silently.
set -u
A=/mnt/TG_2TB/Projects/Apollo/argus
R=/mnt/TG_2TB/Projects/Apollo
M=/mnt/TG_2TB/AI/Models/9b-panel
SERVER=/mnt/TG_2TB/AI/llama_upstream/build_rocm/bin/llama-server
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
OUT=$A/runs/gate9b
mkdir -p "$OUT"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):${LD_LIBRARY_PATH:-}"

start_server () {  # $1=model $2=extra-flags $3=tag
    pkill -x llama-server 2>/dev/null; sleep 8
    # shellcheck disable=SC2086
    setsid nohup "$SERVER" -m "$1" -ngl 99 -c 8192 -fa on -ctk f16 -ctv f16 -np 1 \
        --kv-unified -b 2048 -ub 512 --jinja $2 \
        --host 127.0.0.1 --port 8090 > "$OUT/srv_$3.log" 2>&1 < /dev/null &
    echo $! > "$OUT/srv_$3.pid"
    for i in $(seq 1 120); do
        curl -s -m 2 http://127.0.0.1:8090/health 2>/dev/null | grep -q '"ok"' && break
        sleep 2
    done
    # /props is what you GOT; the flags are what you asked for. AFM-42.
    echo "--- $3 effective sampling (/props) ---"
    curl -s -m 20 http://127.0.0.1:8090/props | python3 -c "
import json,sys
p=json.load(sys.stdin)['default_generation_settings']['params']
print('   ', {k:round(p[k],4) for k in ('temperature','top_k','top_p','min_p','presence_penalty')})"
}

arm () {  # $1=label $2=fixture
    echo "######## $1  $(date -Is)"
    timeout 10800 "$PY" -u "$A/driver.py" \
        --hermes-home "$A/fixtures/$2/agent-home" \
        --fake-root  "$A/fixtures/$2/fake-google" \
        --sandbox    "$A/runs/sandbox_$1" \
        --scenarios  "$A/families_v4.json" \
        --out        "$OUT/$1.jsonl" \
        --events "" --timeout 900 --rep 1 \
        --agent-stderr "$OUT/${1}_agent.log" \
        --agent-cmd "$PY" -m acp_adapter.entry
    echo "   exit=$? rows=$(wc -l < "$OUT/$1.jsonl" 2>/dev/null || echo 0)"
}

MIMO_S="--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 0.0 \
        --chat-template-file $A/templates/mimo_v26_distill_qwen9b_autoparser.jinja"
ORN_S="--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 1.5"

# The lock is a SINGLE GLOBAL FILE and `acquire` overwrites unconditionally -- calling it
# while another benchmark holds it silently steals the lock, and our `release` would then
# strip that run's protection. So: only acquire if free, only release what we acquired.
# Its real job here is keeping the ledger off 127.0.0.1:8090 (its fallback endpoint, and
# our measurement port). A lock held by ANY benchmark already provides that.
LOCK_OWNED=0
if "$R/tools/benchmark_lock.sh" check >/dev/null 2>&1; then
    echo "lock already held: $("$R/tools/benchmark_lock.sh" status 2>&1)"
    echo "  -> NOT acquiring (would clobber), NOT releasing on exit. Protection already in effect."
else
    "$R/tools/benchmark_lock.sh" acquire "9B gate on the 9070" "$$"
    LOCK_OWNED=1
fi

start_server "$M/MiMo-V2.6-Distill-Qwen-9B-Q8_0.gguf" "$MIMO_S" mimo
arm MIMO-a g9mimo
arm MIMO-b g9mimo

start_server "$M/Ornith-1.5-9B-Q8_0.gguf" "$ORN_S" orn
arm ORN-a g9orn
arm ORN-b g9orn

pkill -x llama-server 2>/dev/null
[ "$LOCK_OWNED" = 1 ] && "$R/tools/benchmark_lock.sh" release
echo "######## 9B GATE DONE $(date -Is)"
