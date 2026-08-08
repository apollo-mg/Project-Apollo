#!/usr/bin/env bash
# --reasoning-budget smoke test, PREREG_REASONING_BUDGET_SMOKE.md.
# Six cells: {Bonsai-27B ternary, Gemma-4-12B QAT} x {-1, 0, 1024}.
# Budget -1 runs FIRST per model and is a HARD GATE (G-RB0): if the template does not emit
# reasoning at all, the budget-0 result is uninterpretable and the model is ABORTED, not
# recorded as a pass. Receipts land directly in data/receipts -- never the scratchpad.
set -u
R=/mnt/TG_2TB/Projects/Apollo/data/receipts/battle16gb/reasoning_budget_smoke
MODELS=/mnt/TG_2TB/AI/Models
BONSAI_BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_bonsai/build_hip/bin/llama-server
GEMMA_BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build_rocm/bin/llama-server
PROMPTS="$R/prompts.json"
mkdir -p "$R/cells"

[ -s "$PROMPTS" ] || { echo "FATAL: $PROMPTS missing"; exit 1; }

# label bin model port ctx budget
run_cell() {
  local label=$1 bin=$2 model=$3 port=$4 ctx=$5 budget=$6
  # RB_MAXTOK / RB_EXTRA / RB_TAG support the follow-up cells that separate "the cap works"
  # from "the cap freed room the 2048 ceiling had already taken away", and the MTP-on check.
  local tag="${label}_b${budget/-/m}${RB_TAG:-}"
  local log="$R/cells/${tag}_load.log"
  # Resumable: a cell with a complete jsonl is not re-run (GPU time is the scarce thing).
  if [ -s "$R/cells/${tag}.jsonl" ] && [ "$(wc -l < "$R/cells/${tag}.jsonl")" -eq 8 ]; then
    echo "########## CELL $tag  ALREADY COMPLETE — skipping"; return 0
  fi
  echo "########## CELL $tag  (budget=$budget)  $(date +%H:%M:%S)"
  [ -s "$model" ] || { echo "FATAL: missing $model"; return 1; }

  pkill -x llama-server 2>/dev/null; sleep 4
  # shellcheck disable=SC2086 -- RB_EXTRA is deliberately word-split (extra server args)
  "$bin" -m "$model" -c "$ctx" -ngl 99 -fa on -ctk f16 -ctv f16 --jinja -v \
         --reasoning-format deepseek --reasoning-budget "$budget" ${RB_EXTRA:-} \
         --host 127.0.0.1 --port "$port" > "$log" 2>&1 &

  for i in $(seq 1 120); do
    curl -sf "http://127.0.0.1:$port/health" >/dev/null 2>&1 && break
    sleep 3
  done
  if ! curl -sf "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
    echo "FATAL: $tag server never became ready"; tail -25 "$log"; pkill -x llama-server; return 1
  fi

  # G-RB2: record exactly what was served.
  { echo "cell=$tag budget=$budget"; echo "bin=$bin"; echo "model=$model";
    echo "ctx=$ctx port=$port max_tokens=${RB_MAXTOK:-2048} extra='${RB_EXTRA:-}'";
    grep -am1 "build:" "$log";
    grep -aiE "chat template|reasoning|think" "$log" | head -8; } > "$R/cells/${tag}_serving.txt"

  python3 "$R/rb_probe.py" --endpoint "http://127.0.0.1:$port" --label "$label" \
      --budget "$budget" --prompts "$PROMPTS" --out "$R/cells/${tag}.jsonl" \
      --max-tokens "${RB_MAXTOK:-2048}"
  local rc=$?
  pkill -x llama-server 2>/dev/null; sleep 4
  # -v load logs run ~14 MB/cell and these receipts are committed to a public repo.
  # The boot block carries everything the gates read; the request spam does not.
  if [ -f "$log" ]; then
    head -400 "$log" > "$log.trim" && mv "$log.trim" "$log"
  fi
  echo "=== $tag DONE rc=$rc $(date +%H:%M:%S)"
  return $rc
}

# G-RB0: >=4 of 8 responses must carry reasoning at budget -1, else the model is uninterpretable.
gate_rb0() {
  local f=$1
  python3 - "$f" <<'PY'
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]
ok=[r for r in rows if "error" not in r]
n=sum(1 for r in ok if r.get("has_reasoning"))
print(f"G-RB0: {n}/{len(ok)} responses carried reasoning_content at budget -1")
sys.exit(0 if n>=4 else 1)
PY
}

do_model() {
  local label=$1 bin=$2 model=$3 port=$4 ctx=$5
  run_cell "$label" "$bin" "$model" "$port" "$ctx" -1 || return 1
  if ! gate_rb0 "$R/cells/${label}_bm1.jsonl"; then
    echo "!!!!! $label ABORTED on G-RB0 — template emits no reasoning at budget -1."
    echo "!!!!! Budget-0 output would be uninterpretable. Not recording this model as a pass."
    return 2
  fi
  echo "=== $label G-RB0 PASSED — template is wired for thinking; budget cells are interpretable"
  run_cell "$label" "$bin" "$model" "$port" "$ctx" 0    || return 1
  run_cell "$label" "$bin" "$model" "$port" "$ctx" 1024 || return 1
}

# Usage: rb_smoke.sh [BONSAI|GEMMA|all] [budget]
# A single budget can be run alone so one cell fits inside a bounded foreground call.
# Running a budget cell directly still re-checks G-RB0 first -- the gate is not bypassable.
WHICH=${1:-all}
ONLY_BUDGET=${2:-}

echo "===== reasoning-budget smoke START $(date -Iseconds)  [${WHICH}${ONLY_BUDGET:+ budget=$ONLY_BUDGET}] ====="
rocm-smi --showclocks 2>/dev/null | grep -iE 'sclk|mclk' | head -4 > "$R/cells/clocks.txt"

dispatch() {
  local label=$1 bin=$2 model=$3 port=$4 ctx=$5
  if [ -z "$ONLY_BUDGET" ]; then
    do_model "$label" "$bin" "$model" "$port" "$ctx"; return $?
  fi
  # Single-cell mode: -1 is the gate and may run standalone; any other budget requires
  # a PASSED -1 cell already on disk, else its output is uninterpretable (G-RB0).
  if [ "$ONLY_BUDGET" != "-1" ]; then
    if ! { [ -s "$R/cells/${label}_bm1.jsonl" ] && gate_rb0 "$R/cells/${label}_bm1.jsonl"; }; then
      echo "!!!!! $label: cannot run budget=$ONLY_BUDGET — G-RB0 not established. Run budget -1 first."
      return 2
    fi
  fi
  run_cell "$label" "$bin" "$model" "$port" "$ctx" "$ONLY_BUDGET"
}

if [ "$WHICH" = "all" ] || [ "$WHICH" = "BONSAI" ]; then
  dispatch BONSAI "$BONSAI_BIN" "$MODELS/Bonsai/Ternary-Bonsai-27B-Q2_g64.gguf" 8093 32768
  echo "bonsai_exit=$?" | tee -a "$R/cells/exit_codes.txt"
fi
if [ "$WHICH" = "all" ] || [ "$WHICH" = "GEMMA" ]; then
  dispatch GEMMA "$GEMMA_BIN" "$MODELS/Gemma 4/12B/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf" 8094 16384
  echo "gemma_exit=$?" | tee -a "$R/cells/exit_codes.txt"
fi

echo "===== reasoning-budget smoke DONE $(date -Iseconds) ====="
wc -l "$R"/cells/*.jsonl 2>/dev/null
