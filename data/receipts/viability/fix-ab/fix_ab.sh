#!/usr/bin/env bash
# Interleaved A/B/C: does buun's a334fc01e ("hip: invalidate VBR remaps and clear nonfinite
# recurrent state") stop VBR's post-reset degenerate generations on gfx1201?
# Arms: OLD 3823c9eb6 (positive control), PARENT 2fd7e523b (master minus the fix), FIX a334fc01e.
# Same protocol as ../master-ab/driver_recovered.sh; arm order rotates each rep (Latin square).
# Prereg: ../PREREG_LATCH_INTERLEAVED.md, section "does a334fc01e fix it?".
set -u
OUT=/mnt/TG_2TB/Projects/Apollo/data/receipts/viability/fix-ab
OLDB=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin/llama-server
PARB=/mnt/TG_2TB/Projects/buun-parent/build_rocm/bin/llama-server
FIXB=/mnt/TG_2TB/Projects/buun-master/build_rocm/bin/llama-server
M=/mnt/TG_2TB/AI/Models/gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf
BENCH=/home/mark/projects/hermes-bench-tool-call
PY=$BENCH/.venv/bin/python
DEV=/sys/class/drm/card1/device
HW=$(ls -d $DEV/hwmon/hwmon* | head -1)
LOG=$OUT/driver.log
say(){ echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }
TASK_ARGS=(); while read -r t; do [ -n "$t" ] && TASK_ARGS+=(--task "$t"); done < "$OUT/latch_tasks.txt"

for f in "$OLDB" "$PARB" "$FIXB" "$M" "$PY"; do [ -e "$f" ] || { say "MISSING $f"; exit 1; }; done
[ ${#TASK_ARGS[@]} -eq 24 ] || { say "expected 12 tasks, got $(( ${#TASK_ARGS[@]} / 2 ))"; exit 1; }
say "### fix-ab start: cap $(( $(cat $HW/power1_cap) / 1000000 )) W, vm_update_mode $(cat /sys/module/amdgpu/parameters/vm_update_mode) ###"
for b in OLD:$OLDB PARENT:$PARB FIX:$FIXB; do say "  ${b%%:*}: $("${b#*:}" --version 2>&1 | grep -m1 version)"; done

cleanup(){
  for p in $(pgrep -f '[r]un_agent.py'); do kill -9 "$p" 2>/dev/null; done
  for p in $(pgrep -x llama-server); do kill -TERM "$p" 2>/dev/null; done
  for i in $(seq 1 40); do pgrep -x llama-server >/dev/null || break; sleep 1; done
}
watch_latch(){
  local rd="$1" bp="$2" tag="$3"
  while kill -0 "$bp" 2>/dev/null; do
    sleep 20
    local seq; seq=$($PY - "$rd" <<'PY' 2>/dev/null
import json,glob,os,sys
rows=[]
for f in glob.glob(sys.argv[1]+'/*.json'):
    if os.path.basename(f)=='summary.json': continue
    try: rows.append((os.path.getmtime(f), json.load(open(f)).get('status')))
    except Exception: pass
rows.sort(); print(''.join('I' if s=='INFRA_ERROR' else '.' for _,s in rows))
PY
)
    case "$seq" in *III*) say "  [$tag] LATCH after ${#seq} tasks ($seq) -- aborting early"
        kill -TERM "$bp" 2>/dev/null; sleep 3
        for p in $(pgrep -f '[r]un_agent.py'); do kill -9 "$p" 2>/dev/null; done; return 0;; esac
  done
}
pw(){ cat $HW/power1_average 2>/dev/null || cat $HW/power1_input 2>/dev/null || echo 0; }
sampler(){
  local f="$1"; echo "epoch,power_w,junction_c,sclk" > "$f"
  while :; do
    echo "$(date +%s),$(( $(pw) / 1000000 )),$(( $(cat $HW/temp2_input 2>/dev/null || echo 0) / 1000 )),$(grep '\*' $DEV/pp_dpm_sclk 2>/dev/null | awk '{print $2}')" >> "$f"
    sleep 30
  done
}
run_one(){
  local which="$1" rep="$2"
  local tag="${which}${rep}" B
  case "$which" in OLD) B=$OLDB;; PARENT) B=$PARB;; FIX) B=$FIXB;; esac
  say "=== RUN $tag : $B ==="
  cleanup
  sampler "$OUT/gpu_$tag.csv" &
  local sp=$!
  setsid nohup stdbuf -oL -eL "$B" -m "$M" -ngl 99 -c 32768 -np 1 -fa on --kv-unified \
      -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto -n 4096 \
      --reasoning-effort medium --min-p 0 --jinja \
      --host 127.0.0.1 --port 8090 > "$OUT/server_$tag.log" 2>&1 < /dev/null &
  local ok=0
  for i in $(seq 1 150); do
    curl -s -m 5 http://127.0.0.1:8090/v1/chat/completions -H 'Content-Type: application/json' \
      -d '{"model":"x","messages":[{"role":"user","content":"hi"}],"max_tokens":1}' 2>/dev/null \
      | grep -q finish_reason && { ok=1; break; }
    sleep 3
  done
  if [ $ok -ne 1 ]; then say "  RUN $tag: server never ready"; kill "$sp" 2>/dev/null; cleanup; return 1; fi
  cd "$BENCH"; rm -rf "results/fab_$tag" "traces/fab_$tag" 2>/dev/null
  $PY -m hermesbench run --model "GSQ-RCO-iq3xxs-$tag" --base-url http://127.0.0.1:8090/v1 \
      "${TASK_ARGS[@]}" --toolsets all --timeout-overhead 120 --run-id "fab_$tag" >> "$LOG" 2>&1 &
  local bp=$!; watch_latch "$BENCH/results/fab_$tag" "$bp" "$tag" || true; wait "$bp" 2>/dev/null
  kill "$sp" 2>/dev/null
  cleanup
  say "  RUN $tag complete: vbr resets $(grep -c 'vbr reset:' "$OUT/server_$tag.log"), generations hitting 4096 $(grep -c -E 'eval time = .* / +4096 tokens' "$OUT/server_$tag.log")"
}

say "### interleaved OLD/PARENT/FIX, arm order rotating each rep ###"
run_one OLD 1;    run_one PARENT 1; run_one FIX 1
run_one PARENT 2; run_one FIX 2;    run_one OLD 2
run_one FIX 3;    run_one OLD 3;    run_one PARENT 3
cleanup
say "### FIX A/B COMPLETE ###"
