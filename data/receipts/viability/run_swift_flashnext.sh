#!/usr/bin/env bash
# PREREG_SWIFT_FLASHNEXT.md: base Flash-Next (ISTA GSQ-RCO IQ3_XXS) then Swift 1.5 (UkisAI GSQ-RCO IQ3_XXS) on .194.
# Per arm: server A (MTP off) -> G0 gate (q2_0 g64 load + coherence), speed probe off, stage 1 (M1, thinking off),
# stage 2 (CAL xhigh, 3 seeds); then server B (base MTP head) -> warm-up must draft, speed probe on.
# Every server fresh and VERIFIED (AFM-50): stopped by exact name; own log loaded; /props names the file; 49/49 on GPU.
# Resumable: run_main skips done ids, CAL reps re-run only missing ids, the speed probe re-runs only a missing cell.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; QA="$HERE/../quant-abstention"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"
BIN='~/buun-0b278/build_sm60/bin/llama-server'
FNGB='~/AI/Models/fn_gsq_base/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf'
FNGS='~/AI/Models/fn_gsq_swift/Swift-Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf'
MTP='-md ~/AI/Models/flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3'
FLAGS="-ngl 99 -sm layer -ts 1,1,1,0.6 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0 --port $PORT"
OUT="$HERE/swift_flashnext"; mkdir -p "$OUT"; LOG="$OUT/run.log"; SPEED="$OUT/speed.jsonl"
VAR='{" UNKNOWN": 59322, " Unknown": 21024, " unknown": 9496}'
ALL="CAL-A1,CAL-A2,CAL-A3,CAL-A4,CAL-A5,CAL-A6,CAL-A7,CAL-A8,CAL-U1,CAL-U2,CAL-U3,CAL-U4,CAL-U5,CAL-U6,CAL-U7,CAL-U8"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

stop_server() {
  ssh "$H" 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' \
    || { log "a llama-server survived pkill -- aborting"; exit 1; }
}
trap 'stop_server; scp -q "$H:sfn_*.log" "$OUT/" 2>/dev/null' EXIT

start_server() {   # TAG MODEL EXTRA -> 0 ours and verified; 1 died / not healthy; 2 wrong server / placement
  local tag=$1 model=$2 extra=$3
  stop_server
  ssh "$H" "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $model $FLAGS $extra > ~/sfn_$tag.log 2>&1 < /dev/null &"
  local up=0
  for i in $(seq 1 120); do
    sleep 5
    ssh "$H" 'pgrep -x llama-server >/dev/null' || { log "$tag: server died: $(ssh "$H" "tail -3 ~/sfn_$tag.log")"; return 1; }
    ssh "$H" "grep -q 'model loaded' ~/sfn_$tag.log" && curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }
  done
  [ $up = 1 ] || { log "$tag: not healthy after 600 s"; return 1; }
  local mp
  mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$model")" ] || { log "$tag: WRONG SERVER: $mp"; return 2; }
  ssh "$H" "grep -q 'offloaded 49/49 layers to GPU' ~/sfn_$tag.log" || { log "$tag: placement not 49/49"; return 2; }
  log "$tag: verified -- 49/49 on GPU, $(basename "$mp"), pid $(ssh "$H" 'pgrep -x llama-server'), gpus: $(ssh "$H" 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader' | sort -u | tr '\n' ' ')"
}

gate_g0() {        # TAG -> 0 pass. q2_0 must load as canonical g64 (38 tensors, no Bonsai remap), decode coherently,
  local tag=$1      # and render our request shapes identically to the base arm (the GGUF templates differ; Deviation-free
                    # only if the rendered prompts do not)
  ssh "$H" "grep -qE 'type +q2_0: +38 tensors' ~/sfn_$tag.log" || { log "$tag: G0 FAIL -- no 'type q2_0: 38 tensors' line"; return 1; }
  ssh "$H" "grep -q 'detected PrismML Bonsai group-128' ~/sfn_$tag.log" && { log "$tag: G0 FAIL -- Bonsai g128 remap fired"; return 1; }
  $PY "$HERE/swift_fn_probe.py" gate "$URL" >> "$LOG" 2>&1 || { log "$tag: G0 FAIL -- coherence"; return 1; }
  local rh; rh=$($PY "$HERE/swift_fn_probe.py" render "$URL")
  [ -n "$rh" ] || { log "$tag: G0 FAIL -- render"; return 1; }
  if [ -f "$OUT/render_FNGB.txt" ]; then
    [ "$rh" = "$(cat "$OUT/render_FNGB.txt")" ] || { log "$tag: G0 FAIL -- render $rh differs from base $(cat "$OUT/render_FNGB.txt")"; return 1; }
  else
    echo "$rh" > "$OUT/render_FNGB.txt"
  fi
  log "$tag: G0 pass (q2_0 x38 g64, coherent, render $rh)"
}

missing() {        # ids of ALL not yet in $1
  $PY - "$1" "$ALL" <<'EOF'
import json, os, sys
have = set()
if os.path.exists(sys.argv[1]):
    for l in open(sys.argv[1]):
        try: have.add(json.loads(l)["id"])
        except Exception: pass
print(",".join(i for i in sys.argv[2].split(",") if i not in have))
EOF
}

have_speed() {     # ARM MTP -> 0 if the cell already has 12 rows
  [ -f "$SPEED" ] && [ "$($PY -c 'import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l)["arm"]==sys.argv[2] and json.loads(l)["mtp"]==sys.argv[3]))' "$SPEED" "$1" "$2")" -ge 12 ]
}

warm() { curl -s -m 600 "$URL/v1/chat/completions" -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Say ready."}],"max_tokens":8,"cache_prompt":false,"chat_template_kwargs":{"enable_thinking":false}}' >/dev/null; }

log "== swift flash-next start"
for spec in "FNGB|$FNGB" "FNGS|$FNGS"; do
  IFS='|' read -r arm model <<< "$spec"
  # ---- server A: MTP off
  start_server "${arm}_A" "$model" ""; rc=$?
  [ $rc = 0 ] || { log "$arm: server A rc=$rc -- abort"; exit 1; }
  warm
  gate_g0 "${arm}_A" || exit 1
  have_speed "$arm" off || { log "$arm: speed probe, MTP off"; $PY "$HERE/swift_fn_probe.py" speed "$URL" "$arm" off "$SPEED" >> "$LOG" 2>&1; }
  meta=$($PY -c 'import json,sys; print(json.dumps({"arm": sys.argv[1], "model": sys.argv[2], "build": "buun 0b2789f23 build_sm60", "host": ".194 4x P100 150 W / 1063 MHz", "flags": sys.argv[3]}))' "$arm" "$(basename "$model")" "$FLAGS")
  log "$arm: stage 1 (M1, thinking off)"
  (cd "$QA" && $PY run_main.py --url "$URL" --arm "$arm" --meta "$meta" --expect-variants "$VAR") >> "$OUT/stage1_$arm.log" 2>&1
  log "$arm: stage 1 exit $? ($(($(wc -l < "$QA/raw/main_$arm.jsonl") - 1)) rows)"
  mkdir -p "$OUT/$arm"
  for rep in 1 2 3; do
    ids=$(missing "$OUT/$arm/armA_rep$rep.jsonl"); [ -z "$ids" ] && continue
    log "$arm: stage 2 rep$rep"
    (cd "$HERE" && $PY -u run_fixture_structfix.py --host "$URL" --tier cal --effort xhigh --sampling card \
        --seed $((1000 + rep)) --only "$ids" --arm A --jsonl "$OUT/$arm/armA_rep$rep.jsonl") >> "$OUT/stage2_${arm}_rep$rep.log" 2>&1
    log "$arm: stage 2 rep$rep exit $? ($(wc -l < "$OUT/$arm/armA_rep$rep.jsonl") rows)"
  done
  # ---- server B: MTP on (the base model's head for both arms)
  have_speed "$arm" on && continue
  start_server "${arm}_B" "$model" "$MTP"; rc=$?
  [ $rc = 0 ] || { log "$arm: server B rc=$rc -- MTP leg skipped"; continue; }
  dn=$(curl -s -m 600 "$URL/v1/chat/completions" -H 'content-type: application/json' \
    -d '{"messages":[{"role":"user","content":"Count from 1 to 20."}],"max_tokens":64,"temperature":0,"cache_prompt":false,"chat_template_kwargs":{"enable_thinking":false}}' \
    | $PY -c 'import json,sys; print((json.load(sys.stdin).get("timings") or {}).get("draft_n",0))')
  [ "${dn:-0}" -gt 0 ] || { log "$arm: MTP did not engage (draft_n=$dn) -- MTP leg skipped"; continue; }
  log "$arm: MTP engaged (warm-up draft_n=$dn); speed probe, MTP on"
  $PY "$HERE/swift_fn_probe.py" speed "$URL" "$arm" on "$SPEED" >> "$LOG" 2>&1
done
log "== swift flash-next done"
