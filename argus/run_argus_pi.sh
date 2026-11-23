#!/usr/bin/env bash
# argus families_v5 for the pi-adapter Hermes A/B (data/receipts/pi-hermes/): the same Hermes, the same fixtures, two
# arms side by side -- BASE (Qwen3.8-27B Q8_0, .194 GPUs 0+1 :8190) and PIA (the same file + the pi LoRA, GPUs 2+3 :8191)
# -- reached through an ssh tunnel on 127.0.0.1:8091 / :8092. Thinking off and greedy, set on the servers
# (Hermes sends no sampling or thinking fields to a custom endpoint). Derived from run_argus_v5.sh; that file is untouched.
#   ./run_argus_pi.sh OUTNAME            (ONLY="id1 id2" limits the items; fixtures from build_pi_fixtures.sh, same UTC day)
# PROCESS RULE: kills only PIDs it recorded or verified (stop_194.sh). Never pattern-kills.
set -u
A=/mnt/TG_2TB/Projects/Apollo/argus
R=/mnt/TG_2TB/Projects/Apollo
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
H=10.0.0.194; BIN='~/buun-0b278/build_sm60/bin/llama-server'
BASE_F='~/AI/Models/qwopus/Qwen3.8-27B-Q8_0.gguf'; LORA='~/AI/Models/pi-adapter/Qwen3.8-27B-pi-lora-F16.gguf'
LORA_SHA=a64f91844f19e67da500d8628bdf9383aa334e61b7ab687805802e7d272d7b67
FLAGS="-ngl 99 -sm layer -c 49152 -ctk f16 -ctv f16 -np 1 -fit off --jinja --temp 0 --seed 1 --chat-template-kwargs '{\"enable_thinking\":false}' --host 0.0.0.0"
OUTNAME=${1:?outname}
OUT=$A/runs/pi_$OUTNAME; mkdir -p "$OUT"; LOG=$OUT/run.log
SCEN=$A/families_v5.json
declare -A FX_BASE=([A]=hbA [B]=hbB) FX_PIA=([A]=hpA [B]=hpB)
ITEM_TIMEOUT=${ITEM_TIMEOUT:-3600}
unset HERMES_TIMEZONE
RUN_DATE=$(TZ=UTC date +%F)
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
TUN_PID=""
cleanup() { [ -n "$TUN_PID" ] && kill "$TUN_PID" 2>/dev/null; "$R/argus/gaming/stop_194.sh" >> "$LOG" 2>&1; log "== cleanup done"; }
trap cleanup EXIT

start() {   # NAME GPUS PORT LORA(0/1)
  local extra=""; [ "$4" = 1 ] && extra="--lora $LORA"
  ssh "$H" "CUDA_VISIBLE_DEVICES=$2 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $BASE_F $extra $FLAGS --port $3 > ~/pihermes_$1_$3.log 2>&1 < /dev/null &"
  local i up=0; for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$3/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "ABORT: $1 not healthy on :$3"; exit 1; }
}
preflight() {   # ARM LOCALPORT LORA(0/1): what the agent will actually reach, through the tunnel
  "$PY" - "$2" "$4" "$1" <<'PYEOF' || { log "ABORT: $1 preflight failed"; exit 1; }
import json, sys, urllib.request
port, lora, arm = sys.argv[1], int(sys.argv[2]), sys.argv[3]
u = f"http://127.0.0.1:{port}"
d = json.load(urllib.request.urlopen(u + "/props", timeout=20))
p = d["default_generation_settings"]["params"]
assert d.get("model_path", "").endswith("Qwen3.8-27B-Q8_0.gguf"), d.get("model_path")
assert p["temperature"] == 0, p["temperature"]
n = len(json.load(urllib.request.urlopen(u + "/lora-adapters", timeout=20)))
assert n == lora, f"{arm}: {n} adapters, expected {lora}"
body = json.dumps({"messages": [{"role": "user", "content": "Write one sentence about rivers."}], "max_tokens": 64}).encode()
for k in range(2):   # the first is the discarded warm-up
    r = json.load(urllib.request.urlopen(urllib.request.Request(u + "/v1/chat/completions", body, {"Content-Type": "application/json"}), timeout=300))
m = r["choices"][0]["message"]
assert not (m.get("reasoning_content") or "").strip(), "thinking is on: reasoning_content returned"
print(f"--- {arm}: Q8_0 on :{port} via tunnel, temp 0, {n} adapter(s), thinking off, warm-up discarded")
PYEOF
}

arm() {   # LABEL FXMAP-NAME  -- every item with a pristine agent-home restored before EACH item
  local L=$1; local -n FXM=$2
  local items; items=$("$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));print(' '.join(x['id']+'@'+x['world'] for x in d['scenarios']))" "$SCEN")
  for iw in $items; do
    local id=${iw%@*} w=${iw#*@}; local FX=${FXM[$w]}
    if [ -n "${ONLY:-}" ] && [[ " $ONLY " != *" $id "* ]]; then continue; fi
    local SNAP="$A/fixtures/$FX.agent-home.pristine.tar"
    local sk="$A/fixtures/$FX/agent-home/skills/google/google-workspace/SKILL.md"
    grep -q "\"id\": \"$id\"" "$OUT/$L.jsonl" 2>/dev/null && continue    # resume
    [ "$(TZ=UTC date +%F)" = "$RUN_DATE" ] || { log "ABORT ($L): UTC date rolled over"; return 1; }
    rm -rf "$A/fixtures/$FX/agent-home"; tar -xf "$SNAP" -C "$A/fixtures/$FX"
    [ "$(sha256sum < "$A/fixtures/$FX/agent-home/config.yaml")" = "$(tar -xOf "$SNAP" agent-home/config.yaml | sha256sum)" ] || { log "ABORT ($L): restore mismatch"; return 1; }
    grep -q "fixtures/$FX/fake-google" "$sk" || { log "ABORT ($L): SKILL.md not bound to $FX"; return 1; }
    "$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));json.dump({'scenarios':[x for x in d['scenarios'] if x['id']==sys.argv[2]]},open(sys.argv[3],'w'))" "$SCEN" "$id" "$OUT/.one_$L.json"
    "$PY" -u "$A/driver.py" \
        --hermes-home "$A/fixtures/$FX/agent-home" --fake-root "$A/fixtures/$FX/fake-google" \
        --sandbox "$A/runs/sandbox_$FX" --scenarios "$OUT/.one_$L.json" \
        --out "$OUT/$L.jsonl" --events "$OUT/${L}_events.jsonl" \
        --timeout "$ITEM_TIMEOUT" --rep 1 --agent-stderr "$OUT/${L}_agent.log" \
        --agent-cmd "$A/sandboxed_agent.sh" "$PY" -m acp_adapter.entry >> "$OUT/${L}_driver.log" 2>&1
    local rc=$?
    [ $rc = 5 ] && { log "ABORT ($L): driver found a leftover host listener after $id"; return 1; }
    log "$L $id rc=$rc $(tail -1 "$OUT/$L.jsonl" 2>/dev/null | "$PY" -c 'import json,sys;r=json.loads(sys.stdin.read());print(r["verdict"], r["secs"], "s")' 2>/dev/null)"
  done
  log "$L rows=$(wc -l < "$OUT/$L.jsonl" 2>/dev/null)"
}

# ---- isolation guards (as run_argus_v5.sh), for every fixture of both arms
for v in BROWSER_CDP_URL AGENT_BROWSER_ENGINE BROWSER_USE_API_KEY; do [ -n "${!v:-}" ] && { echo "ABORT: $v is set"; exit 1; }; done
command -v bwrap >/dev/null && [ -x "$A/sandboxed_agent.sh" ] || { echo "ABORT: sandbox missing"; exit 1; }
for spec in hbA:8091 hbB:8091 hpA:8092 hpB:8092; do
  FX=${spec%:*}; P=${spec#*:}; HH="$A/fixtures/$FX/agent-home"
  [ -f "$A/fixtures/$FX.agent-home.pristine.tar" ] || { echo "ABORT: no pristine snapshot for $FX (run build_pi_fixtures.sh)"; exit 1; }
  grep -q "AFM-44" "$HH/config.yaml" || { echo "ABORT: $FX predates AFM-44"; exit 1; }
  grep -q "base_url: http://127.0.0.1:$P/v1" "$HH/config.yaml" || { echo "ABORT: $FX not pointed at :$P"; exit 1; }
  grep -q "AFM-45" "$A/fixtures/$FX/fake-google/reset.sh" || { echo "ABORT: $FX reset.sh not stripped"; exit 1; }
  "$A/fixtures/$FX/fake-google/reset.sh" >/dev/null && ! grep -q -i -E "ambiguity|_note|isomorph|EXTRA" "$A/fixtures/$FX/fake-google/state.json" \
    || { echo "ABORT: $FX stripped state leaks authoring notes"; exit 1; }
  # rebase_seed.py snaps the world to the anchor's weekday (Thursday) on or after the build's UTC date: it must be the
  # Thursday that follows THIS run's UTC date, or the fixture was built for another day
  want=$("$PY" -c "import datetime as d,sys;n=d.date.fromisoformat(sys.argv[1]);print(n+d.timedelta((3-n.weekday())%7))" "$RUN_DATE")
  got=$("$PY" -c "import json,sys;print(json.load(open(sys.argv[1])).get('_rebased',{}).get('to'))" "$A/fixtures/$FX/fake-google/fixtures/seed.json")
  [ "$got" = "$want" ] || { echo "ABORT: $FX world anchored to $got, this run needs $want (rebuild fixtures)"; exit 1; }
done
for p in 8091 8092; do curl -s -m 2 "http://127.0.0.1:$p/health" >/dev/null 2>&1 && { echo "ABORT: something already answers on :$p"; exit 1; }; done

log "== pi Hermes A/B ($OUTNAME) start, code $(git -C "$R" rev-parse --short HEAD), UTC date $RUN_DATE"
"$R/tools/s194.sh" on >> "$LOG" 2>&1 || { log "ABORT: .194 did not come up"; exit 1; }
ok=0; for i in $(seq 1 40); do
  if [ "$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$H" 'echo ready' 2>/dev/null)" = ready ]; then ok=$((ok + 1)); else ok=0; fi
  [ $ok -ge 3 ] && break; sleep 10
done
[ $ok -ge 3 ] || { log "ABORT: ssh not stable"; exit 1; }
st=$(ssh "$H" 'pgrep -x llama-server >/dev/null && echo RUNNING || echo CLEAR' 2>/dev/null); [ "$st" = CLEAR ] || { log "ABORT: server check '$st'"; exit 1; }
h=$(ssh "$H" "sha256sum $LORA | cut -d' ' -f1"); [ "$h" = "$LORA_SHA" ] || { log "ABORT: adapter hash $h"; exit 1; }
start BASE 0,1 8190 0; start PIA 2,3 8191 1
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8091:127.0.0.1:8190 -L 127.0.0.1:8092:127.0.0.1:8191 "$H" &
TUN_PID=$!; sleep 3; kill -0 "$TUN_PID" 2>/dev/null || { log "ABORT: tunnel did not start"; exit 1; }
preflight BASE 8091 x 0 >> "$LOG" 2>&1; preflight PIA 8092 x 1 >> "$LOG" 2>&1
log "servers, tunnel and preflight ok"
arm BASE FX_BASE &
PA=$!
arm PIA FX_PIA &
PB=$!
echo "$PA $PB" > "$OUT/arm.pids"
wait "$PA" "$PB"
log "== done: BASE $(wc -l < "$OUT/BASE.jsonl" 2>/dev/null) rows, PIA $(wc -l < "$OUT/PIA.jsonl" 2>/dev/null) rows"
