#!/usr/bin/env bash
# Runs ENTIRELY ON .194 (setsid-detached) so a control-plane reboot cannot kill it.
# Rebuild of run_queue_after_puzzle.sh, whose stage-1 results were lost when /tmp was
# wiped by the desktop reboot on 2026-07-25 ~23:35 EDT.
#
#   STAGE 1  thinking-suppression 2x2 factorial (Laguna Q2)   — re-run, results were lost
#   STAGE 2  ThinkingCap vs stock Qwen3.6-27B accuracy A/B    — stock arm was killed ~88min in
#
# STAGE 1 rationale (unchanged): Tom/BlackwellBoy infer TWO thinking suppressors — named persona
# and "coding-shaped tasks" — but every one of their measurements came from a pipeline passing
# tool schemas each turn. Our 492-sample run (maximally coding-shaped, default template system
# msg, NO tools) fired ~100%. Laguna's template branches on tools. 2x2 separates the variables
# they co-varied.
#
# SANDBOX NOTE: generated code now executes on .194 (py3.14.4 / numpy 2.4.6, dual Xeon
# E5-2650v3) instead of the desktop (py3.14.6 / numpy 2.4.3, 5700X3D). Neither pending stage
# compares EXEC_TIMEOUT against the Puzzle/Laguna receipts — stage 1 barely executes code and
# stage 2 is internally matched — but the 60s exec timeout is on slower cores here. Any FUTURE
# leg meant to compare against data/receipts/humaneval-plus/ must account for this.
set -u
STAGES="${HEP_STAGES:-12}"      # which stages to run, e.g. "1", "2", "12"
HEP=/home/mark/hep
OUT=$HEP/out
EP=http://127.0.0.1:8091
LOG=$OUT/queue.log
PY=/home/mark/venv/bin/python3
CTL=/home/mark/ab_server.sh

LAGUNA="/home/mark/AI/Models/Laguna/Laguna-S-2.1-UD-Q2_K_XL.gguf"
POOLSIDE_BIN="/home/mark/poolside-llama/build/bin/llama-server"
STOCK="/home/mark/AI/Models/Qwen 3.6/27B/Qwen3.6-27B-Q8_0.gguf"
TC="/home/mark/AI/Models/Qwen 3.6/27B-ThinkingCap/ThinkingCap-Qwen3.6-27B-Q8_0-MTP.gguf"
SUBSET="HumanEval/0,HumanEval/10,HumanEval/20,HumanEval/30,HumanEval/40,HumanEval/50,HumanEval/60,HumanEval/70,HumanEval/80,HumanEval/100,HumanEval/110,HumanEval/120,HumanEval/130,HumanEval/140,HumanEval/150"
PERSONA="You are a senior software engineer. Write clean, correct, production-quality Python."
TOOLS='[{"type":"function","function":{"name":"read_file","description":"Read a file from the workspace.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"File path"}},"required":["path"]}}},{"type":"function","function":{"name":"write_file","description":"Write content to a file in the workspace.","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},{"type":"function","function":{"name":"run_command","description":"Run a shell command and return its output.","parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}}]'

say () { echo "[$(date '+%F %T')] $*" >> "$LOG"; }
srv_stop () { bash "$CTL" stop >> "$LOG" 2>&1; sleep 8; }
srv_start () { bash "$CTL" start "$1" "${2:-}" >> "$LOG" 2>&1; }
wait_health () { for i in $(seq 1 90); do curl -s -m 5 $EP/health 2>/dev/null | grep -q '"ok"' && return 0; sleep 10; done; return 1; }
show_model () { curl -s -m 10 $EP/props 2>/dev/null | $PY -c "import sys,json;print('   loaded:',json.load(sys.stdin).get('model_path','?').split('/')[-1])" >> "$LOG" 2>&1; }
clocks () { nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader | tr '\n' ' ' >> "$LOG"; echo >> "$LOG"; }

say "=== REBUILT QUEUE START (running on .194, detached) stages=$STAGES ==="
clocks
srv_stop

########## STAGE 1 — 2x2 factorial: persona x tools ##########
if [[ "$STAGES" == *1* ]]; then
say "=== STAGE 1: thinking-suppression 2x2 (Laguna Q2, thinking nominally ON) ==="
srv_start "$LAGUNA" "$POOLSIDE_BIN"
if wait_health; then
  show_model
  cell () {   # cell <tag> <label> ; HEP_SYSTEM/HEP_TOOLS exported by caller
    say "  cell: $2"
    HEP_MODEL="Laguna-Q2-$1" HEP_ENDPOINT="$EP/v1/chat/completions" \
    HEP_TEMP=0.7 HEP_TOP_P=0.95 HEP_TOP_K=20 HEP_K=1 HEP_ONLY="$SUBSET" \
    HEP_PREFIX=sup HEP_TAG="$1" $PY "$HEP/hep_eval.py" >> "$OUT/sup_$1.log" 2>&1
    grep -h "THINKING FIRED" "$OUT/sup_$1.log" >> "$LOG" 2>&1
  }
  ( unset HEP_SYSTEM HEP_TOOLS;                      cell base    "default sys, NO tools  (our published condition)" )
  ( export HEP_SYSTEM="$PERSONA"; unset HEP_TOOLS;   cell persona "PERSONA sys, NO tools  (Tom suppressor 1)" )
  ( unset HEP_SYSTEM; export HEP_TOOLS="$TOOLS";     cell tools   "default sys, TOOLS     (the untested variable)" )
  ( export HEP_SYSTEM="$PERSONA" HEP_TOOLS="$TOOLS"; cell both    "PERSONA sys + TOOLS    (real agent pipeline)" )
  say "--- STAGE 1 SUMMARY ---"
  grep -h "THINKING FIRED" "$OUT"/sup_base.log "$OUT"/sup_persona.log "$OUT"/sup_tools.log "$OUT"/sup_both.log >> "$LOG" 2>&1
else
  say "STAGE 1: Laguna server never healthy — SKIPPED"
fi
srv_stop
fi

########## STAGE 2 — ThinkingCap vs stock ##########
run_arm () {
  local name="$1" model="$2" tag="$3"
  say "=== STAGE 2 arm: $name ==="
  clocks
  srv_start "$model"
  wait_health || { say "  $name: server never healthy — skipping arm"; srv_stop; return 1; }
  show_model
  ( unset HEP_SYSTEM HEP_TOOLS
    HEP_MODEL="$name" HEP_ENDPOINT="$EP/v1/chat/completions" \
    HEP_TEMP=1.0 HEP_TOP_P=0.95 HEP_TOP_K=20 HEP_MIN_P=0.0 HEP_K=3 \
    HEP_PREFIX=tcab HEP_TAG="$tag" $PY "$HEP/hep_eval.py" >> "$OUT/tcab_${tag}.log" 2>&1 )
  say "  $name harness exit=$?"
  tail -8 "$OUT/tcab_${tag}.log" >> "$LOG" 2>&1
  srv_stop
}
if [[ "$STAGES" == *2* ]]; then
  run_arm "Qwen3.6-27B-Q8_0-STOCK"       "$STOCK" "stock"
  run_arm "ThinkingCap-Qwen3.6-27B-Q8_0" "$TC"    "tc"
fi

say "=== ALL STAGES COMPLETE ==="
grep -hE "pass@1 POOLED|THINKING FIRED" "$OUT"/sup_*.log "$OUT"/tcab_*.log 2>/dev/null >> "$LOG"
clocks
say "=== SIGNAL: rebuilt queue done ==="
