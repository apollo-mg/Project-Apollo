#!/usr/bin/env bash
# 2x2 brevity test on .194. See data/receipts/argus-v2/PREREG_HEMMINGWAY_BREVITY.md
#   cells: stock/hemm x brevity-SOUL/none, 2 reps, order soul,none | none,soul
# Process rule: only PIDs this script recorded are ever signalled. No pattern kills.
# Teardown on ANY exit: stop the .194 servers, power the node off, and verify with the
# probe that cannot pass while the node is up -- `s194.sh status` -> chassis: off (AFM-40).
set -u
A=/mnt/TG_2TB/Projects/Apollo/argus; R=/mnt/TG_2TB/Projects/Apollo
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
OUT=$A/runs/brev; mkdir -p "$OUT"
H=10.0.0.194
log () { echo "== $(date -Is) $*"; }
CELLPIDS=()

stop_servers () {
    ssh -o BatchMode=yes $H 'for p in ~/argus_brev_*.pid; do [ -f "$p" ] && { kill "$(cat "$p")" 2>/dev/null; rm -f "$p"; }; done; sleep 8
        for i in $(seq 1 20); do [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null)" ] && break; sleep 3; done
        nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr "\n" " "' 2>/dev/null
    echo
}
teardown () {
    log "teardown"
    for p in "${CELLPIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null; done
    stop_servers
    "$R/tools/s194.sh" off 2>&1 | tail -2
    for i in $(seq 1 12); do
        st=$("$R/tools/s194.sh" status 2>/dev/null | sed -n 's/^chassis *: *//p')
        [ "$st" = off ] && { log "VERIFIED: .194 chassis off"; return; }
        sleep 10
    done
    log "!! could NOT verify .194 is off (last: '$st') -- check it by hand"
}
trap teardown EXIT

# ---- guards: isolation, fixtures, model identity ----
for v in BROWSER_CDP_URL AGENT_BROWSER_ENGINE BROWSER_USE_API_KEY; do
    [ -n "${!v:-}" ] && { log "ABORT: $v set"; exit 1; }; done
command -v bwrap >/dev/null && [ -x "$A/sandboxed_agent.sh" ] || { log "ABORT: sandbox unavailable"; exit 1; }
for fx in h2ssoul h2hsoul h2snone h2hnone; do
    Hm="$A/fixtures/$fx/agent-home"
    [ "$(grep -hoE 'fixtures/[A-Za-z0-9]+/fake-google' "$Hm/skills/google/google-workspace/SKILL.md" | sort -u)" = "fixtures/$fx/fake-google" ] || { log "ABORT: $fx SKILL.md backend"; exit 1; }
    grep -q AFM-44 "$Hm/config.yaml" && grep -q "hard_stop_enabled: true" "$Hm/config.yaml" && grep -q AFM-45 "$A/fixtures/$fx/fake-google/reset.sh" || { log "ABORT: $fx harness config"; exit 1; }
done
[ -f "$A/fixtures/h2ssoul/agent-home/SOUL.md" ] && [ -f "$A/fixtures/h2hsoul/agent-home/SOUL.md" ] && [ ! -e "$A/fixtures/h2snone/agent-home/SOUL.md" ] && [ ! -e "$A/fixtures/h2hnone/agent-home/SOUL.md" ] || { log "ABORT: SOUL placement wrong"; exit 1; }
sz=$(ssh -o BatchMode=yes $H 'stat -c %s ~/models/Qwen3.8-27B-Q5_K_M.gguf ~/models/Altworld_Hemmingway-1-Q5_K_M.gguf' | tr '\n' ' ')
[ "$sz" = "20923877088 20923877440 " ] || { log "ABORT: model bytes '$sz'"; exit 1; }
log "guards passed; models byte-exact"

start_servers () {
    stop_servers
    ssh -o BatchMode=yes $H 'setsid ~/start_arm.sh brev_stock ~/models/Qwen3.8-27B-Q5_K_M.gguf 8084 0,1 0 </dev/null >/dev/null 2>&1; setsid ~/start_arm.sh brev_hemm ~/models/Altworld_Hemmingway-1-Q5_K_M.gguf 8085 2,3 1 </dev/null >/dev/null 2>&1'
    ssh -o BatchMode=yes $H 'for f in argus_brev_stock argus_brev_hemm; do for i in $(seq 1 120); do grep -q "listening on" ~/$f.log 2>/dev/null && break; grep -qiE "error|abort" ~/$f.log 2>/dev/null && { echo "$f FAILED"; exit 1; }; sleep 3; done; done' || { log "ABORT: server start failed"; exit 1; }
    for P in 8084 8085; do   # discard one warmup generation: the first request after a load is unreliable
        curl -s -m 180 "http://$H:$P/v1/chat/completions" -H 'Content-Type: application/json' \
          -d '{"messages":[{"role":"user","content":"say ready"}],"max_tokens":64}' >/dev/null
    done
    for pair in "8084 Qwen3.8-27B-Q5_K_M.gguf" "8085 Altworld_Hemmingway-1-Q5_K_M.gguf"; do
        set -- $pair
        curl -s -m 30 "http://$H:$1/props" | python3 -c "
import json,sys
d=json.load(sys.stdin); g=d['default_generation_settings']; p=g['params']
got={k:round(p[k],4) for k in ('temperature','top_k','top_p','min_p','presence_penalty')}
want={'temperature':1.0,'top_k':20,'top_p':0.95,'min_p':0.05,'presence_penalty':0.0}
ok = got==want and g.get('n_ctx')==65536 and '$2' in d.get('model_path','')
print('  :$1', d.get('model_path','').split('/')[-1], 'n_ctx', g.get('n_ctx'), got, 'OK' if ok else 'MISMATCH')
sys.exit(0 if ok else 1)" || { log "ABORT: /props mismatch on :$1"; exit 1; }
    done
}

cell () {  # $1=label $2=fixture $3=rep   (backgrounded by phase)
    timeout 14400 "$PY" -u "$A/driver.py" \
        --hermes-home "$A/fixtures/$2/agent-home" --fake-root "$A/fixtures/$2/fake-google" \
        --sandbox "$A/runs/sandbox_brev_$1" --scenarios "$A/families_v4.json" \
        --out "$OUT/$1.jsonl" --events "$OUT/$1_r$3_events.jsonl" \
        --timeout 900 --rep "$3" --agent-stderr "$OUT/$1_agent.log" \
        --agent-cmd "$A/sandboxed_agent.sh" "$PY" -m acp_adapter.entry > "$OUT/$1_r$3.console" 2>&1
    echo "   cell $1 rep $3 exit=$? rows=$(wc -l < "$OUT/$1.jsonl" 2>/dev/null || echo 0)"
}

phase () {  # $1=soul|none $2=rep
    log "######## phase prompt=$1 rep=$2"
    start_servers
    if [ "$1" = soul ]; then cell stock_soul h2ssoul "$2" & c1=$!; cell hemm_soul h2hsoul "$2" & c2=$!
    else                    cell stock_none h2snone "$2" & c1=$!; cell hemm_none h2hnone "$2" & c2=$!; fi
    CELLPIDS=($c1 $c2); wait $c1 $c2; CELLPIDS=()
    stop_servers
}

LOCK_OWNED=0
if "$R/tools/benchmark_lock.sh" check >/dev/null 2>&1; then
    log "lock held elsewhere ($("$R/tools/benchmark_lock.sh" status 2>&1)) -- not taking it"
else "$R/tools/benchmark_lock.sh" acquire "hemmingway brevity 2x2" "$$"; LOCK_OWNED=1; fi

phase soul 1
phase none 1
phase none 2
phase soul 2
log "######## ALL PHASES DONE"
[ "$LOCK_OWNED" = 1 ] && "$R/tools/benchmark_lock.sh" release
