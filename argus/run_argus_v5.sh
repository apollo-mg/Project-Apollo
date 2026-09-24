#!/usr/bin/env bash
# argus families_v5 runner: two worlds, fixture chosen PER ITEM from the item's "world" field.
#   ./run_argus_v5.sh OUTNAME LABEL:MTP:SEED [LABEL:MTP:SEED ...]     e.g.  val OFF-s1:0:1
# Derived from run_mtp_agentic.sh (left untouched: it may be running). Differences:
#  - world A items -> fixture mtpag, world B items -> fixture mtpagB (each with its own pristine snapshot)
#  - NO TZ / HERMES_TIMEZONE pin: the driver pins the agent's TZ to the world zone (UTC) and Hermes then
#    reports UTC. The GMT+12 pin of 2026-09-23 told the model "UTC-12" against a UTC world (correction in
#    RESULT_MTP_AGENTIC.md). Guard: every item asserts the UTC date has not rolled over.
#  - prompt cache OFF (outcome runs); CACHE=1 turns it on
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
OUTNAME=${1:?outname}; shift
OUT=$A/runs/v5_$OUTNAME
CACHEFLAG=(--no-cache-prompt); [ "${CACHE:-0}" = 1 ] && CACHEFLAG=()
SCEN=$A/families_v5.json
declare -A FXOF=([A]=mtpag [B]=mtpagB)
ITEM_TIMEOUT=${ITEM_TIMEOUT:-2400}   # set from the smoke; far above either arm's need
mkdir -p "$OUT"
export LD_LIBRARY_PATH="$(dirname "$SERVER"):${LD_LIBRARY_PATH:-}"
unset HERMES_TIMEZONE
RUN_DATE=$(TZ=UTC date +%F)   # the date the agent is shown (driver pins TZ=UTC)
SRVPID="$OUT/srv.pid"

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
    local items; items=$("$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));print(' '.join(x['id']+'@'+x['world'] for x in d['scenarios']))" "$SCEN")
    for iw in $items; do
        local id=${iw%@*} w=${iw#*@}; local FX=${FXOF[$w]}
        local HOME_SNAP="$A/fixtures/$FX.agent-home.pristine.tar"
        local sk="$A/fixtures/$FX/agent-home/skills/google/google-workspace/SKILL.md"
        grep -q "\"id\": \"$id\"" "$OUT/$1.jsonl" 2>/dev/null && continue    # resume
        [ "$(TZ=UTC date +%F)" = "$RUN_DATE" ] || { echo "ABORT: UTC date rolled over ($RUN_DATE -> $(TZ=UTC date +%F)); the agent would see a new day"; exit 1; }
        rm -rf "$A/fixtures/$FX/agent-home"; tar -xf "$HOME_SNAP" -C "$A/fixtures/$FX"
        [ "$(sha256sum < "$A/fixtures/$FX/agent-home/config.yaml")" = "$(tar -xOf "$HOME_SNAP" agent-home/config.yaml | sha256sum)" ] || { echo "ABORT: agent-home restore mismatch"; exit 1; }
        grep -q "fixtures/$FX/fake-google" "$sk" || { echo "ABORT: SKILL.md not bound to $FX"; exit 1; }
        "$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));json.dump({'scenarios':[x for x in d['scenarios'] if x['id']==sys.argv[2]]},open(sys.argv[3],'w'))" "$SCEN" "$id" "$OUT/.one.json"
        "$PY" -u "$A/driver.py" \
            --hermes-home "$A/fixtures/$FX/agent-home" \
            --fake-root  "$A/fixtures/$FX/fake-google" \
            --sandbox    "$A/runs/sandbox_$FX" \
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

# ---- isolation guards (AFM-44 / AFM-45), for EVERY fixture this corpus uses
for v in BROWSER_CDP_URL AGENT_BROWSER_ENGINE BROWSER_USE_API_KEY; do
    [ -n "${!v:-}" ] && { echo "ABORT: $v is set in the environment"; exit 1; }
done
command -v bwrap >/dev/null || { echo "ABORT: bwrap missing"; exit 1; }
[ -x "$A/sandboxed_agent.sh" ] || { echo "ABORT: sandboxed_agent.sh missing"; exit 1; }
for FX in "${FXOF[@]}"; do
    H="$A/fixtures/$FX/agent-home"
    [ -f "$A/fixtures/$FX.agent-home.pristine.tar" ] || { echo "ABORT: no pristine snapshot for $FX"; exit 1; }
    grep -q "AFM-44" "$H/config.yaml" || { echo "ABORT: $FX predates AFM-44 deny rules"; exit 1; }
    grep -q "base_url: http://127.0.0.1:$PORT/v1" "$H/config.yaml" || { echo "ABORT: $FX not pointed at :$PORT"; exit 1; }
    grep -q "AFM-45" "$A/fixtures/$FX/fake-google/reset.sh" || { echo "ABORT: $FX reset.sh not stripped"; exit 1; }
    "$A/fixtures/$FX/fake-google/reset.sh" >/dev/null && ! grep -q -i -E "ambiguity|_note|isomorph|EXTRA" "$A/fixtures/$FX/fake-google/state.json" \
        || { echo "ABORT: $FX stripped state leaks authoring notes"; exit 1; }
    echo "isolation ok: $FX pristine home $(sha256sum < "$A/fixtures/$FX.agent-home.pristine.tar" | cut -c1-12)"
done
[ -z "${HERMES_TIMEZONE:-}" ] || { echo "ABORT: HERMES_TIMEZONE set"; exit 1; }

if "$R/tools/benchmark_lock.sh" check >/dev/null 2>&1; then
    echo "ABORT: benchmark lock held: $("$R/tools/benchmark_lock.sh" status 2>&1)"; exit 1
fi
"$R/tools/benchmark_lock.sh" acquire "argus v5 ($OUTNAME) on the 9070" "$$" >/dev/null; LOCK_OWNED=1

for spec in "$@"; do     # LABEL:MTP:SEED
    IFS=: read -r L MTP SEED <<< "$spec"
    start_server "$SEED" "$MTP" "$(echo "$L" | tr 'A-Z' 'a-z')"; arm "$L"
done
echo "######## ARGUS V5 ($OUTNAME) DONE $(date -Is)"
