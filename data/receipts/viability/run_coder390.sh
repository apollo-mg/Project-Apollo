#!/usr/bin/env bash
# PREREG_CODER390_UNSOLVABLE.md -- one lane of the .194 campaign.   usage: run_coder390.sh preflight | A | B
#   preflight (once, before either lane): free disk, GPU pairing, fetch both GGUFs at the pinned revisions, sha256 of all
#   three against the registered values (G-1). Writes coder390/gates/preflight.txt; any failure exits 1.
#   lane A = GPUs 0,1, port 8191:  B (UNS x2 seeds, CAL x3) -> BC (thinking-cap reruns on B)
#   lane B = GPUs 2,3, port 8192:  G1 (B, two rows) -> N (UNS x2, CAL x3) -> P (UNS x2, CAL x3)
# Every arm on one scheme: 2-GPU tensor split, f16 KV, -c 20480, -np 1, MTP off, buun 0b2789f23, cache_prompt false.
# One fresh VERIFIED server per pass (AFM-26 uptime, AFM-50 identity), stopped by the PID recorded at launch and never
# by name: the other lane's llama-server shares the box. A canary before and after every pass. Resumable: a pass runs
# only the ids missing from its jsonl.
set -uo pipefail
LANE=$1
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 $H"
BIN='~/buun-0b278/build_sm60/bin/llama-server'
B_GGUF='~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf'
N_GGUF='/dev/shm/coder390/Qwen3.8-27B-Coder390-EfficientThink-Q6_K-MTP.gguf'   # tmpfs: / has 19 GB free
P_GGUF='/dev/shm/coder390/Qwen3.8-27B-EfficientThink-SimPO-Q6_K.gguf'
B_SHA=562fbf760503008f118e5df38de5b3e97992d1f693f475815631198547486727
N_SHA=302597c53d1b00f7230b53a8a050831390a4371e92a80c1ac644fa920af76ab1
P_SHA=20c4f349b0a355e6b7725d9a6ee7a862172d5081a8284b4defb1c5e5955ca5bc
N_URL=https://huggingface.co/nerkyor/Qwen3.8-27B-Coder390-EfficientThink-Opus5.5-GPT6Astra-Grok4.7-DSV4Pro-K3-SFT-RLOO-MTP-DFlash2/resolve/b85739f2e2ee71dd090265493a8ffad5ce321083/GGUF/Qwen3.8-27B-Coder390-EfficientThink-Q6_K-MTP.gguf
P_URL=https://huggingface.co/nerkyor/Qwen3.8-27B-EfficientThink-Uncensored-K3-Opus5-Grok4.6-GPT5.6Sol-SFT-SimPO-DFlash2/resolve/882e1af3b8f5844f3b3163b132e343c06e91908f/GGUF/Q6_K/Qwen3.8-27B-EfficientThink-SimPO-Q6_K.gguf
case $LANE in
  A) GPUS=0,1; PORT=8191 ;;
  B) GPUS=2,3; PORT=8192 ;;
  preflight) GPUS=; PORT=0 ;;
  *) echo "usage: $0 preflight|A|B"; exit 2 ;;
esac
URL="http://$H:$PORT"
FLAGS="-ngl 99 -c 20480 -np 1 -fa on --kv-unified -ctk f16 -ctv f16 -sm tensor -fit off --jinja -lv 4 --host 0.0.0.0 --port $PORT"
OUT="$HERE/coder390"; mkdir -p "$OUT"/{B,N,P,BC,gates}
LOG="$OUT/run_lane$LANE.log"; CANARY="$OUT/canary.jsonl"
UNS_FX="$HERE/fixture_unsolvable.json"; CAL_FX="$HERE/fixture_v0_beta.json"
log() { echo "$(date '+%F %T') [lane $LANE] $*" | tee -a "$LOG"; }

stop_server() {    # only the PID this lane recorded, and only if it is still a llama-server
  local pid; pid=$($SSH "cat ~/c390_lane$LANE.pid 2>/dev/null")
  [ -n "$pid" ] || return 0
  $SSH "[ \"\$(cat /proc/$pid/comm 2>/dev/null)\" = llama-server ] && kill $pid; \
        for i in \$(seq 1 60); do [ \"\$(cat /proc/$pid/comm 2>/dev/null)\" = llama-server ] || exit 0; sleep 1; done; exit 1" \
    || { log "llama-server $pid survived SIGTERM -- aborting"; exit 1; }
  $SSH "rm -f ~/c390_lane$LANE.pid"
}
[ "$LANE" = preflight ] || trap 'stop_server; scp -q "$H:c390_${LANE}_*.log" "$OUT/gates/" 2>/dev/null' EXIT

start_server() {   # TAG MODEL -> 0 ours and verified; 1 died / not healthy; 2 wrong server / placement / context
  local tag=$1 model=$2 up=0
  stop_server
  $SSH "CUDA_VISIBLE_DEVICES=$GPUS GGML_CUDA_ALLREDUCE=internal nohup setsid $BIN -m $model $FLAGS \
        > ~/c390_${LANE}_$tag.log 2>&1 < /dev/null & echo \$! > ~/c390_lane$LANE.pid"
  for i in $(seq 1 120); do
    sleep 5
    $SSH "[ \"\$(cat /proc/\$(cat ~/c390_lane$LANE.pid)/comm 2>/dev/null)\" = llama-server ]" \
      || { log "$tag: server died: $($SSH "tail -3 ~/c390_${LANE}_$tag.log")"; return 1; }
    $SSH "grep -q 'model loaded' ~/c390_${LANE}_$tag.log" && curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }
  done
  [ $up = 1 ] || { log "$tag: not healthy after 600 s"; return 1; }
  local props mp nctx
  props=$(curl -s -m 10 "$URL/props")
  mp=$(echo "$props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  nctx=$(echo "$props" | $PY -c 'import json,sys; d=json.load(sys.stdin); print((d.get("default_generation_settings") or {}).get("n_ctx") or d.get("n_ctx"))')
  [ "$(basename "$mp")" = "$(basename "$model")" ] || { log "$tag: WRONG SERVER: $mp"; return 2; }
  [ "$nctx" = 20480 ] || { log "$tag: n_ctx $nctx, not 20480"; return 2; }
  $SSH "grep -qE 'offloaded ([0-9]+)/\\1 layers to GPU' ~/c390_${LANE}_$tag.log" || { log "$tag: not every layer on GPU"; return 2; }
  log "$tag: verified -- $(basename "$mp"), n_ctx $nctx, pid $($SSH "cat ~/c390_lane$LANE.pid"), GPUs $GPUS, \
$($SSH "grep -oE 'offloaded [0-9]+/[0-9]+ layers to GPU' ~/c390_${LANE}_$tag.log | head -1"), \
clocks: $($SSH "nvidia-smi -i $GPUS --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader" | sort -u | tr '\n' ' ')"
}

canary() {         # ARM PASS PHASE -> one row: thinking off, temp 0, fixed prompt; content hash and decode rate
  $PY - "$URL" "$LANE" "$1" "$2" "$3" "$CANARY" <<'EOF'
import hashlib, json, os, sys, time, urllib.request
url, lane, arm, pss, phase, out = sys.argv[1:]
body = {"messages": [{"role": "user", "content": "Count from 1 to 20, separated by commas."}], "max_tokens": 96,
        "temperature": 0, "seed": 1, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
t0 = time.time()
r = json.load(urllib.request.urlopen(urllib.request.Request(url + "/v1/chat/completions", json.dumps(body).encode(),
                                                            {"content-type": "application/json"}), timeout=600))
tm = r.get("timings") or {}
c = r["choices"][0]["message"].get("content") or ""
row = {"lane": lane, "arm": arm, "pass": pss, "phase": phase, "t": time.strftime("%F %T"), "wall_s": round(time.time() - t0, 2),
       "sha": hashlib.sha256(c.encode()).hexdigest()[:16], "predicted_n": tm.get("predicted_n"),
       "tok_s": tm.get("predicted_per_second"), "draft_n": tm.get("draft_n")}
with open(out, "a") as f:
    f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
print(json.dumps(row))
EOF
}

canary_ok() {      # ARM PASS -> 0 if the post canary matches the pre canary's text and keeps >= 0.7x its decode rate
  $PY - "$CANARY" "$LANE" "$1" "$2" <<'EOF'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
m = [r for r in rows if (r["lane"], r["arm"], r["pass"]) == tuple(sys.argv[2:5])]
pre = [r for r in m if r["phase"] == "pre"][-1]; post = [r for r in m if r["phase"] == "post"][-1]
ok = pre["sha"] == post["sha"] and (post["tok_s"] or 0) >= 0.7 * (pre["tok_s"] or 0)
print(f"canary {'ok' if ok else 'SUSPECT'}: pre {pre['tok_s']:.2f} tok/s {pre['sha']}, post {post['tok_s']:.2f} tok/s {post['sha']}")
sys.exit(0 if ok else 1)
EOF
}

gate_g0() {        # ARM TAG -> coherent decode, MTP not drafting, and a render hash equal to the base arm's
  local arm=$1 tag=$2 rh dn
  $PY "$HERE/swift_fn_probe.py" gate "$URL" >> "$LOG" 2>&1 || { log "$tag: G0 FAIL -- coherence"; return 1; }
  dn=$(canary "$arm" g0 g0 | $PY -c 'import json,sys; print(json.loads(sys.stdin.read()).get("draft_n") or 0)')
  [ "${dn:-0}" = 0 ] || { log "$tag: G0 FAIL -- draft_n=$dn: something is drafting"; return 1; }
  rh=$($PY "$HERE/swift_fn_probe.py" render "$URL")
  [ -n "$rh" ] || { log "$tag: G0 FAIL -- render"; return 1; }
  echo "$rh" > "$OUT/gates/render_${arm}_lane$LANE.txt"
  if [ "$arm" != B ]; then
    [ "$rh" = "$(cat "$OUT/gates/render_B_laneA.txt")" ] || { log "$tag: G0 FAIL -- render $rh != base $(cat "$OUT/gates/render_B_laneA.txt")"; return 1; }
  fi
  log "$tag: G0 pass (coherent, draft_n 0, render $rh)"
}

missing() {        # JSONL FIXTURE [IDS] -> fixture ids (or the given subset) not yet in JSONL
  $PY - "$1" "$2" "${3:-}" <<'EOF'
import json, os, sys
have = set()
if os.path.exists(sys.argv[1]):
    for l in open(sys.argv[1]):
        try: have.add(json.loads(l)["id"])
        except Exception: pass
ids = [i["id"] for i in json.load(open(sys.argv[2]))["tier_cal"]["items"]]
if sys.argv[3]: ids = [i for i in ids if i in sys.argv[3].split(",")]
print(",".join(i for i in ids if i not in have))
EOF
}

fixture_pass() {   # ARM MODEL TIER(uns|cal) SEED [CAP] [IDS] [RETRY] -- one pass on a fresh server
  local arm=$1 model=$2 tier=$3 seed=$4 cap=${5:-} subset=${6:-} retry=${7:-0}
  local fx=$UNS_FX; [ "$tier" = cal ] && fx=$CAL_FX
  local jl="$OUT/$arm/${tier}_seed$seed.jsonl" pss="${tier}_$seed" ids rc
  ids=$(missing "$jl" "$fx" "$subset"); [ -z "$ids" ] && { log "$arm $pss: complete"; return 0; }
  start_server "${arm}_$pss" "$model"; rc=$?
  [ $rc = 0 ] || { log "$arm $pss: server rc=$rc -- abort"; exit 1; }
  if [ ! -f "$OUT/gates/g0_${arm}_lane$LANE" ]; then gate_g0 "$arm" "${arm}_$pss" || exit 1; touch "$OUT/gates/g0_${arm}_lane$LANE"; fi
  canary "$arm" "$pss" pre >> "$LOG"
  log "$arm $pss: $(echo "$ids" | tr ',' '\n' | wc -l) items${cap:+, thinking cap $cap}"
  (cd "$HERE" && $PY -u run_fixture_structfix.py --host "$URL" --fixture "$fx" --tier cal --effort xhigh --sampling card \
      --seed "$seed" --no-cache-prompt --only "$ids" --arm "$arm" --jsonl "$jl" ${cap:+--budget $cap}) \
      >> "$OUT/$arm/${tier}_seed$seed.log" 2>&1
  log "$arm $pss: exit $? ($(wc -l < "$jl") rows)"
  canary "$arm" "$pss" post >> "$LOG"
  if ! canary_ok "$arm" "$pss" >> "$LOG" 2>&1; then
    if [ "$retry" = 0 ]; then         # registered: quarantine the pass's rows and re-run it ONCE on a fresh server
      mv "$jl" "$jl.quarantine1"
      log "$arm $pss: CANARY SUSPECT -- rows moved to $(basename "$jl").quarantine1; re-running the pass once"
      fixture_pass "$arm" "$model" "$tier" "$seed" "$cap" "$subset" 1
    else
      log "$arm $pss: CANARY SUSPECT on the re-run too -- rows kept and flagged SUSPECT in the receipt"
      echo "$arm $pss" >> "$OUT/gates/suspect_passes.txt"
    fi
  fi
}

preflight() {      # G-1: run once before either lane
  local pf="$OUT/gates/preflight.txt" ok=1 topo got
  : > "$pf"
  pflog() { echo "$*" | tee -a "$pf"; }
  pflog "preflight $(date '+%F %T')"
  pflog "free: $($SSH "mkdir -p /dev/shm/coder390 && df -BG --output=avail /dev/shm/coder390 | tail -1 | tr -d ' G'") GB in /dev/shm (needs 47)"
  topo=$($SSH "nvidia-smi topo -m" | sed 's/\x1b\[[0-9;]*m//g')
  echo "$topo" >> "$pf"
  echo "$topo" | awk '$1=="GPU0"{a=$3} $1=="GPU2"{b=$5} END{exit !(a=="PHB" && b=="PHB")}' \
    && pflog "GPU pairs 0-1 and 2-3: PHB" || { pflog "FAIL: GPU 0-1 / 2-3 are not PHB pairs"; ok=0; }
  for spec in "$N_URL|$N_GGUF|23177516384" "$P_URL|$P_GGUF|22082530048"; do
    IFS='|' read -r url dst size <<< "$spec"
    [ "$($SSH "stat -c %s $dst 2>/dev/null")" = "$size" ] && { pflog "have  $(basename "$dst") ($size bytes)"; continue; }
    pflog "fetch $(basename "$dst") ($size bytes)"
    $SSH "curl -sSL --fail --retry 5 -C - -o $dst '$url'" || { pflog "FAIL: download $(basename "$dst")"; ok=0; }
  done
  for spec in "$B_GGUF|$B_SHA" "$N_GGUF|$N_SHA" "$P_GGUF|$P_SHA"; do
    IFS='|' read -r f want <<< "$spec"
    got=$($SSH "sha256sum $f 2>/dev/null | cut -d' ' -f1")
    [ "$got" = "$want" ] && pflog "sha256 ok   $(basename "$f") ${want:0:12}" || { pflog "FAIL: sha256 $(basename "$f") got '${got:0:12}' want ${want:0:12}"; ok=0; }
  done
  pflog "binary: $($SSH "ls -l --time-style=+%F $BIN | awk '{print \$6, \$7}'")"
  [ $ok = 1 ] && pflog "PREFLIGHT PASS" || { pflog "PREFLIGHT FAIL"; exit 1; }
}

if [ "$LANE" = preflight ]; then preflight; exit 0; fi
grep -q "PREFLIGHT PASS" "$OUT/gates/preflight.txt" 2>/dev/null || { echo "run preflight first"; exit 1; }
log "== start (GPUs $GPUS, port $PORT)"
if [ "$LANE" = A ]; then
  for s in 1001 1002; do fixture_pass B "$B_GGUF" uns $s; done
  for s in 1001 1002 1003; do fixture_pass B "$B_GGUF" cal $s; done
  CAP=$($PY "$HERE/analyze_coder390.py" cap "$OUT") || { log "cap rule failed -- BC skipped"; CAP=; }
  if [ -n "$CAP" ]; then
    log "BC: thinking cap $CAP (rule: 1.5 x P90 of B's solvable UNS completion tokens, up to a multiple of 256)"
    echo "$CAP" > "$OUT/BC/cap.txt"
    # G2: determinism + the cap binds. Two rows the cap cannot reach must come back byte-identical to B's; then every
    # B row whose completion exceeded the cap is re-run with it (the rest are byte-identical copies by construction).
    start_server BC_g2 "$B_GGUF" || exit 1
    (cd "$HERE" && $PY -u run_fixture_structfix.py --host "$URL" --fixture "$UNS_FX" --tier cal --effort xhigh --sampling card \
        --seed 1001 --no-cache-prompt --only "$($PY "$HERE/analyze_coder390.py" g2ids "$OUT" uns 1001 "$CAP")" --arm BC \
        --jsonl "$OUT/gates/g2_uns_seed1001.jsonl" --budget "$CAP") >> "$OUT/gates/g2.log" 2>&1
    $PY "$HERE/analyze_coder390.py" g2check "$OUT" >> "$LOG" 2>&1 && G2=pass || G2=fail
    log "G2 $G2"
    $PY "$HERE/analyze_coder390.py" bcplan "$OUT" "$CAP" "$G2" | while read -r tier seed ids; do
      fixture_pass BC "$B_GGUF" "$tier" "$seed" "$CAP" "$ids"
    done
  fi
else
  # G1: lane identity. Lane B serves the base arm for two rows that lane A also runs (UNS-S1, UNS-S2, seed 1001);
  # the analysis compares them byte for byte. Wait for lane A's G0 so the base render hash exists first.
  for i in $(seq 1 360); do [ -f "$OUT/gates/render_B_laneA.txt" ] && break; sleep 10; done
  [ -f "$OUT/gates/render_B_laneA.txt" ] || { log "lane A never passed G0 -- abort"; exit 1; }
  start_server B_g1 "$B_GGUF" || exit 1
  (cd "$HERE" && $PY -u run_fixture_structfix.py --host "$URL" --fixture "$UNS_FX" --tier cal --effort xhigh --sampling card \
      --seed 1001 --no-cache-prompt --only UNS-S1,UNS-S2 --arm B_laneB --jsonl "$OUT/gates/g1_laneB.jsonl") >> "$OUT/gates/g1.log" 2>&1
  log "G1 rows written ($(wc -l < "$OUT/gates/g1_laneB.jsonl"))"
  for s in 1001 1002; do fixture_pass N "$N_GGUF" uns $s; done
  for s in 1001 1002 1003; do fixture_pass N "$N_GGUF" cal $s; done
  for s in 1001 1002; do fixture_pass P "$P_GGUF" uns $s; done
  for s in 1001 1002 1003; do fixture_pass P "$P_GGUF" cal $s; done
fi
log "== lane $LANE done"
