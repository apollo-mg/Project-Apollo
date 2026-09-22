#!/usr/bin/env bash
# 9B gate on the RX 9070. See data/receipts/argus-9b/PREREG_9B_GATE.md (+ amendment).
#   ./run_9b_gate.sh smoke   -> 3 items per model, event trace on, for shakedown
#   ./run_9b_gate.sh         -> the preregistered 4 arms x 40 items
#
# PROCESS RULE: this script kills ONLY the server whose PID it recorded. It never
# pattern-kills. On 2026-09-22 a redundant `safekill --force driver.py` killed a
# concurrent experiment's drivers; safekill protects self and ancestors, and has no
# way to know another run owns processes matching the same pattern.
set -u
A=/mnt/TG_2TB/Projects/Apollo/argus
R=/mnt/TG_2TB/Projects/Apollo
M=/mnt/TG_2TB/AI/Models/9b-panel
SERVER=$R/engines/buun-llama-cpp/build_rocm/bin/llama-server   # buun 38ada0e1b
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
MODE=${1:-full}
OUT=$A/runs/gate9b${MODE:+_$MODE}; [ "$MODE" = full ] && OUT=$A/runs/gate9b
mkdir -p "$OUT"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):${LD_LIBRARY_PATH:-}"
SRVPID="$OUT/srv.pid"

stop_server () {
    [ -f "$SRVPID" ] || return 0
    local p; p=$(cat "$SRVPID")
    kill "$p" 2>/dev/null
    for i in $(seq 1 30); do kill -0 "$p" 2>/dev/null || break; sleep 1; done
    rm -f "$SRVPID"; sleep 5          # let VRAM actually release
}

LOCK_OWNED=0
cleanup () { stop_server; [ "$LOCK_OWNED" = 1 ] && "$R/tools/benchmark_lock.sh" release; }
trap cleanup EXIT

start_server () {  # $1=model path  $2=sampling+template flags  $3=tag
    stop_server
    if curl -s -m 2 http://127.0.0.1:8090/health >/dev/null 2>&1; then
        echo "ABORT: something NOT started by this script is answering on :8090"; exit 1
    fi
    # -c 65536: Hermes hard-refuses < 64,000 ctx. VBR t4: f16 at 64k won't fit 16 GB;
    # VBR enters at f16 and degrades only when the budget binds. --no-cache-prompt:
    # VBR + warm prefix cache alternates outputs, and this measures a noise floor.
    # shellcheck disable=SC2086
    setsid nohup "$SERVER" -m "$1" -ngl 99 -c 65536 -fa on -np 1 --kv-unified \
        -ctk vbr -ctv vbr --vbr-floor t4 --no-cache-prompt \
        -b 2048 -ub 512 --jinja $2 \
        --host 127.0.0.1 --port 8090 > "$OUT/srv_$3.log" 2>&1 < /dev/null &
    echo $! > "$SRVPID"
    for i in $(seq 1 150); do
        curl -s -m 2 http://127.0.0.1:8090/health 2>/dev/null | grep -q '"ok"' && break
        kill -0 "$(cat "$SRVPID")" 2>/dev/null || { echo "ABORT: $3 server died"; tail -5 "$OUT/srv_$3.log"; exit 1; }
        sleep 2
    done
    # /props is what you GOT, not what you asked for (AFM-42). Also refuse to measure
    # a model other than the one intended (the MIMO-off mislabel, 2026-09-22).
    curl -s -m 20 http://127.0.0.1:8090/props | python3 -c "
import json,sys
d=json.load(sys.stdin); g=d['default_generation_settings']; p=g['params']
mp=d.get('model_path','')
print('--- $3 /props: model', mp.split('/')[-1])
print('    n_ctx', g.get('n_ctx'), {k:round(p[k],4) for k in ('temperature','top_k','top_p','min_p','presence_penalty')})
sys.exit(0 if '$(basename "$1")' in mp else 1)" || { echo "ABORT: /props model_path is not $(basename "$1")"; exit 1; }
}

arm () {  # $1=label  $2=fixture
    echo "######## $1  $(date -Is)"
    # The fixture's SKILL.md bakes an ABSOLUTE path to the fake backend. A fixture copied
    # with cp instead of built by make_fixture.sh keeps the SOURCE fixture's path, so the
    # agent's actions land in another world and a correct run scores WRONG-INACTION
    # (happened 2026-09-22: MiMo's correct gmail.reply was recorded in pilotA's state).
    local sk="$A/fixtures/$2/agent-home/skills/google/google-workspace/SKILL.md"
    local own; own=$(grep -hoE 'fixtures/[A-Za-z0-9]+/fake-google' "$sk" | sort -u)
    [ "$own" = "fixtures/$2/fake-google" ] || { echo "ABORT: $sk writes to [$own], not fixtures/$2"; exit 1; }
    timeout 14400 "$PY" -u "$A/driver.py" \
        --hermes-home "$A/fixtures/$2/agent-home" \
        --fake-root  "$A/fixtures/$2/fake-google" \
        --sandbox    "$A/runs/sandbox_$1" \
        --scenarios  "$SCEN" \
        --out        "$OUT/$1.jsonl" \
        --events     "$OUT/${1}_events.jsonl" \
        --timeout 900 --rep 1 \
        --agent-stderr "$OUT/${1}_agent.log" \
        --agent-cmd "$PY" -m acp_adapter.entry
    echo "   exit=$? rows=$(wc -l < "$OUT/$1.jsonl" 2>/dev/null || echo 0)"
}

# AFM-44 isolation. A working browser can never reach the fake mailbox -- only the
# real web -- so no test agent may inherit one. Hermes reads BROWSER_CDP_URL from the
# ENVIRONMENT (test agents inherit ours) and browser.cdp_url from config; either would
# hand every model a live browser. Also refuse any fixture built before the deny rules.
for v in BROWSER_CDP_URL AGENT_BROWSER_ENGINE BROWSER_USE_API_KEY; do
    [ -n "${!v:-}" ] && { echo "ABORT: $v is set in the environment -- test agents would inherit a browser"; exit 1; }
done
for fx in g9mimo g9orn; do
    H="$A/fixtures/$fx/agent-home"
    grep -qE "^\s*(BROWSER_CDP_URL|AGENT_BROWSER_ENGINE|BROWSER_USE_API_KEY)=" "$H/.env" 2>/dev/null \
        && { echo "ABORT: $fx/.env sets a browser endpoint or key"; exit 1; }
    grep -qE "^\s*cdp_url:" "$H/config.yaml" && { echo "ABORT: $fx config sets browser.cdp_url"; exit 1; }
    grep -q "AFM-44" "$H/config.yaml" || { echo "ABORT: $fx predates the AFM-44 browser deny rules"; exit 1; }
done
echo "isolation: no browser endpoint in env or fixtures; deny rules present"

MIMO_S="--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 0.0 \
        --chat-template-file $A/templates/mimo_v26_distill_qwen9b_autoparser.jinja"
ORN_S="--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 1.5"

if [ "$MODE" = smoke ]; then
    SCEN="$OUT/smoke_scenarios.json"
    python3 - "$A/families_v4.json" "$SCEN" <<'PYEOF'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src))
items = d if isinstance(d, list) else d.get("items", d.get("scenarios", []))
want = ["f1-referent-r1", "f2-lookup-r2", "f4-unsat-r1"]   # r1 is where MiMo looped
sub = [i for i in items if i.get("id") in want]
assert len(sub) == len(want), [i.get("id") for i in sub]
out = sub if isinstance(d, list) else {**d, **({"items": sub} if "items" in d else {"scenarios": sub})}
json.dump(out, open(dst, "w"), indent=1)
print("smoke subset:", [i["id"] for i in sub])
PYEOF
    MIMO_ARMS="MIMO-smoke"; ORN_ARMS="ORN-smoke"
else
    SCEN="$A/families_v4.json"
    MIMO_ARMS="MIMO-a MIMO-b"; ORN_ARMS="ORN-a ORN-b"
fi

# Lock: single global file whose acquire overwrites unconditionally. Only take it if
# free; only release what we took. Its job here is keeping the ledger off :8090.
if "$R/tools/benchmark_lock.sh" check >/dev/null 2>&1; then
    echo "lock held elsewhere: $("$R/tools/benchmark_lock.sh" status 2>&1) -- not taking it"
else
    "$R/tools/benchmark_lock.sh" acquire "9B gate ($MODE) on the 9070" "$$"; LOCK_OWNED=1
fi

start_server "$M/MiMo-V2.6-Distill-Qwen-9B-Q8_0.gguf" "$MIMO_S" mimo
for L in $MIMO_ARMS; do arm "$L" g9mimo; done
start_server "$M/Ornith-1.5-9B-Q8_0.gguf" "$ORN_S" orn
for L in $ORN_ARMS; do arm "$L" g9orn; done
echo "######## 9B GATE ($MODE) DONE $(date -Is)"
