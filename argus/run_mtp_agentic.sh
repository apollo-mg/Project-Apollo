#!/usr/bin/env bash
# MTP on vs off, multi-turn agent outcomes. data/receipts/mtp-agentic/PREREG_MTP_AGENTIC.md
#   ./run_mtp_agentic.sh smoke   -> 3 items: OFF-s1 twice (determinism) + MTP-s1 once (timing)
#   ./run_mtp_agentic.sh         -> OFF/MTP x seeds 1,2,3, alternating, 40 items each
#   ./run_mtp_agentic.sh cache   -> same, PROMPT CACHE ON, for time-to-completion (PREREG_MTP_AGENTIC_SPEED.md)
#
# PROCESS RULE: kills ONLY the server PID it recorded. Never pattern-kills.
# PORT 8091, not 8090: Open WebUI on this desktop is configured for :8090.
set -u
A=/mnt/TG_2TB/Projects/Apollo/argus
R=/mnt/TG_2TB/Projects/Apollo
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.8/27B/Qwen3.8-27B-UD-IQ3_XXS.gguf"
SERVER=$R/engines/buun-llama-cpp/build_rocm/bin/llama-server   # buun 38ada0e1b
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
PORT=8091
FX=mtpag
MODE=${1:-full}
OUT=$A/runs/mtpag${MODE:+_$MODE}; [ "$MODE" = full ] && OUT=$A/runs/mtpag
CACHEFLAG=(--no-cache-prompt); [ "$MODE" = cache ] && CACHEFLAG=()   # speed run: realistic serving
ITEM_TIMEOUT=${ITEM_TIMEOUT:-2400}   # set from the smoke; far above either arm's need
mkdir -p "$OUT"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):${LD_LIBRARY_PATH:-}"
# The fake world is weekday-anchored and the agent sees the real clock, so an overnight run
# would give arms before and after midnight a different "today". UTC-12 keeps the calendar
# date fixed for ~18 h from a US-afternoon start; every item asserts it has not rolled over.
export TZ=Etc/GMT+12 HERMES_TIMEZONE=Etc/GMT+12
RUN_DATE=$(date +%F)
SRVPID="$OUT/srv.pid"
HOME_SNAP="$A/fixtures/$FX.agent-home.pristine.tar"

stop_server () {
    [ -f "$SRVPID" ] || return 0
    local p; p=$(cat "$SRVPID")
    kill "$p" 2>/dev/null
    for i in $(seq 1 40); do kill -0 "$p" 2>/dev/null || break; sleep 1; done
    kill -0 "$p" 2>/dev/null && kill -9 "$p"
    rm -f "$SRVPID"; sleep 5
}
LOCK_OWNED=0
cleanup () { stop_server; [ "$LOCK_OWNED" = 1 ] && [ "$(cut -f1 "$R/run/benchmark.lock" 2>/dev/null)" = "$$" ] && rm -f "$R/run/benchmark.lock"; }
trap cleanup EXIT

start_server () {  # $1=seed  $2=mtp(0/1)  $3=tag
    stop_server
    curl -s -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { echo "ABORT: something else answers on :$PORT"; exit 1; }
    local spec=()
    [ "$2" = 1 ] && spec=(--spec-type draft-mtp --spec-draft-n-max 2)
    # Static turbo4 KV (not VBR): identical, deterministic KV in both arms; VBR's schedule would
    # differ between arms because the drafter changes free VRAM (drafter-gates-kv-budget).
    # --no-cache-prompt: warm prefix cache + speculation is bistable (argus 08826ad6 finding).
    setsid nohup "$SERVER" -m "$MODEL" -ngl 99 -c 65536 -fa on -np 1 \
        -ctk turbo4 -ctv turbo4 "${CACHEFLAG[@]}" -b 2048 -ub 512 --jinja \
        --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --presence-penalty 0.0 \
        --seed "$1" --chat-template-kwargs '{"reasoning_effort":"medium"}' "${spec[@]}" \
        --host 127.0.0.1 --port "$PORT" > "$OUT/srv_$3.log" 2>&1 < /dev/null &
    echo $! > "$SRVPID"
    for i in $(seq 1 150); do
        curl -s -m 2 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && break
        kill -0 "$(cat "$SRVPID")" 2>/dev/null || { echo "ABORT: $3 server died"; tail -5 "$OUT/srv_$3.log"; exit 1; }
        sleep 2
    done
    # /props is what you GOT (AFM-42); discard one warmup (server-uptime rule) and assert
    # the arm label matches whether drafting actually happened (the MIMO-off mislabel).
    "$PY" - "$PORT" "$2" "$1" "$3" <<'PYEOF' || { echo "ABORT: $3 preflight failed"; exit 1; }
import json, sys, urllib.request
port, mtp, seed, tag = sys.argv[1], sys.argv[2] == "1", int(sys.argv[3]), sys.argv[4]
d = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/props", timeout=20))
g = d["default_generation_settings"]; p = g["params"]
assert "UD-IQ3_XXS" in d.get("model_path", ""), d.get("model_path")
assert abs(p["temperature"] - 0.6) < 1e-6 and p["top_k"] == 20 and p["seed"] == seed, p
body = json.dumps({"messages": [{"role": "user", "content": "Write one sentence about rivers."}],
                   "max_tokens": 64, "chat_template_kwargs": {"enable_thinking": False}}).encode()
r = json.load(urllib.request.urlopen(urllib.request.Request(
    f"http://127.0.0.1:{port}/v1/chat/completions", body, {"Content-Type": "application/json"}), timeout=120))
dn = r["timings"].get("draft_n") or 0
assert bool(dn) == mtp, f"arm says mtp={mtp} but draft_n={dn}"
print(f"--- {tag}: model ok, seed {p['seed']}, temp {p['temperature']}, warmup discarded, draft_n={dn}")
PYEOF
}

arm () {  # $1=label   runs every item with a pristine agent-home restored before EACH item
    echo "######## $1  $(date -Is)"
    local sk="$A/fixtures/$FX/agent-home/skills/google/google-workspace/SKILL.md"
    local items; items=$("$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));i=d if isinstance(d,list) else d.get('items',d.get('scenarios'));print(' '.join(x['id'] for x in i))" "$SCEN")
    for id in $items; do
        grep -q "\"id\": \"$id\"" "$OUT/$1.jsonl" 2>/dev/null && continue    # resume
        [ "$(date +%F)" = "$RUN_DATE" ] || { echo "ABORT: agent calendar date rolled over ($RUN_DATE -> $(date +%F))"; exit 1; }
        rm -rf "$A/fixtures/$FX/agent-home"; tar -xf "$HOME_SNAP" -C "$A/fixtures/$FX"
        [ "$(sha256sum < "$A/fixtures/$FX/agent-home/config.yaml")" = "$CFG_SHA" ] || { echo "ABORT: agent-home restore mismatch"; exit 1; }
        grep -q "fixtures/$FX/fake-google" "$sk" || { echo "ABORT: SKILL.md not bound to $FX"; exit 1; }
        "$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));i=d if isinstance(d,list) else d.get('items',d.get('scenarios'));one=[x for x in i if x['id']==sys.argv[2]];json.dump(one if isinstance(d,list) else {**d,('items' if 'items' in d else 'scenarios'):one},open(sys.argv[3],'w'))" "$SCEN" "$id" "$OUT/.one.json"
        "$PY" -u "$A/driver.py" \
            --hermes-home "$A/fixtures/$FX/agent-home" \
            --fake-root  "$A/fixtures/$FX/fake-google" \
            --sandbox    "$A/runs/sandbox_mtpag" \
            --scenarios  "$OUT/.one.json" \
            --out        "$OUT/$1.jsonl" \
            --events     "$OUT/${1}_events.jsonl" \
            --timeout "$ITEM_TIMEOUT" --rep 1 \
            --agent-stderr "$OUT/${1}_agent.log" \
            --agent-cmd "$A/sandboxed_agent.sh" "$PY" -m acp_adapter.entry >> "$OUT/${1}_driver.log" 2>&1
        rc=$?
        [ $rc = 5 ] && { echo "ABORT: driver found a leftover host listener after $id"; exit 1; }
        echo "   $id rc=$rc $(tail -1 "$OUT/$1.jsonl" 2>/dev/null | "$PY" -c 'import json,sys;r=json.loads(sys.stdin.read());print(r["verdict"], r["secs"], "s")' 2>/dev/null)"
    done
    echo "   $1 rows=$(wc -l < "$OUT/$1.jsonl")"
}

# ---- isolation guards (AFM-44 / AFM-45), as in run_9b_gate.sh
for v in BROWSER_CDP_URL AGENT_BROWSER_ENGINE BROWSER_USE_API_KEY; do
    [ -n "${!v:-}" ] && { echo "ABORT: $v is set in the environment"; exit 1; }
done
command -v bwrap >/dev/null || { echo "ABORT: bwrap missing"; exit 1; }
[ -x "$A/sandboxed_agent.sh" ] || { echo "ABORT: sandboxed_agent.sh missing"; exit 1; }
[ -f "$HOME_SNAP" ] || { echo "ABORT: no pristine agent-home snapshot $HOME_SNAP"; exit 1; }
H="$A/fixtures/$FX/agent-home"
grep -q "AFM-44" "$H/config.yaml" || { echo "ABORT: fixture predates AFM-44 deny rules"; exit 1; }
grep -q "base_url: http://127.0.0.1:$PORT/v1" "$H/config.yaml" || { echo "ABORT: fixture not pointed at :$PORT"; exit 1; }
grep -q "AFM-45" "$A/fixtures/$FX/fake-google/reset.sh" || { echo "ABORT: reset.sh not stripped"; exit 1; }
CFG_SHA=$(tar -xOf "$HOME_SNAP" agent-home/config.yaml | sha256sum)
echo "isolation ok; pristine home $(sha256sum < "$HOME_SNAP" | cut -c1-12)"

if "$R/tools/benchmark_lock.sh" check >/dev/null 2>&1; then
    echo "ABORT: benchmark lock held: $("$R/tools/benchmark_lock.sh" status 2>&1)"; exit 1
fi
"$R/tools/benchmark_lock.sh" acquire "mtp-agentic ($MODE) on the 9070" "$$" >/dev/null; LOCK_OWNED=1

if [ "$MODE" = smoke ]; then
    SCEN="$OUT/smoke_scenarios.json"
    "$PY" - "$A/families_v4.json" "$SCEN" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1])); items = d if isinstance(d, list) else d.get("items", d.get("scenarios"))
want = ["f1-referent-r1", "f2-lookup-r2", "f4-unsat-r1"]
sub = [i for i in items if i["id"] in want]; assert len(sub) == 3
json.dump(sub if isinstance(d, list) else {**d, ("items" if "items" in d else "scenarios"): sub}, open(sys.argv[2], "w"))
PYEOF
    start_server 1 0 off1;  arm OFF-s1
    start_server 1 0 off1b; arm OFF-s1-repeat
    start_server 1 1 mtp1;  arm MTP-s1
else
    SCEN="$A/families_v4.json"
    for s in 1 2 3; do
        start_server "$s" 0 "off$s"; arm "OFF-s$s"
        start_server "$s" 1 "mtp$s"; arm "MTP-s$s"
    done
fi
echo "######## MTP-AGENTIC ($MODE) DONE $(date -Is)"
