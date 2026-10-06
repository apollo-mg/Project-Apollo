#!/usr/bin/env bash
# PREREG_STRATA_9070.md runner. usage: run_strata.sh ARM CONFIG.json PROMPT_FILE [lmx extra flags...]
# Fresh Strata server per arm (PID recorded, killed by PID) with the shared thinking setting "none" ->
# wait for /health loaded -> g4_proxy.py capture -> lmx remote speed test (1 warmup + 3 timed, median).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; OUT="$HERE/runs"; mkdir -p "$OUT"; LOG="$OUT/run.log"
ST=/mnt/TG_2TB/Projects/strata; PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
PROXY="$HERE/../gemma4-9070-spec/g4_proxy.py"; HW="$HERE/../gemma4-9070-spec/hw_9070xt.json"
ARM=$1; CFG=$2; PFILE=$3; shift 3
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
echo '{"reasoning_effort": "none"}' > "${CFG%.json}.shared-settings.json"
(cd "$ST" && exec "$ST/.venv/bin/python" serve/server.py --engine strata --config "$CFG" --port 8080) > "$OUT/server_$ARM.log" 2>&1 &
SP=$!; echo $SP > "$OUT/server.pid"
cleanup() { kill ${PP:-} 2>/dev/null; kill $SP 2>/dev/null; for i in $(seq 1 60); do kill -0 $SP 2>/dev/null || break; sleep 1; done; }
trap cleanup EXIT
t0=$(date +%s); up=0
for i in $(seq 1 900); do
  kill -0 $SP 2>/dev/null || break
  h=$(curl -s -m 2 http://127.0.0.1:8080/health); case "$h" in *'"loaded": true'*|*'"loaded":true'*) up=1; break;; esac
  sleep 1
done
[ $up = 1 ] || { log "$ARM: not loaded after $(( $(date +%s) - t0 ))s: $(tail -3 "$OUT/server_$ARM.log" | tr '\n' ' ' | cut -c1-300)"; exit 1; }
model=$(echo "$h" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model"))')
ram=$(free -g | awk '/^Mem:/{print "used "$3" avail "$7" GB"}'); vram=$(rocm-smi --showmeminfo vram 2>/dev/null | awk -F': ' '/Total Used/{printf "%.2f", $NF/1e9}')
log "$ARM: loaded in $(( $(date +%s) - t0 ))s; model $model; RAM $ram; VRAM used $vram GB; config $(basename "$CFG")"
$PY "$PROXY" 8097 8080 "$OUT/capture_$ARM.jsonl" & PP=$!
for i in $(seq 1 20); do curl -sf -m 2 http://127.0.0.1:8097/health >/dev/null && break; sleep 0.5; done
lmx speed-test run custom --mode remote --base-url http://127.0.0.1:8097 --hf-id ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF \
  --quantization IQ1_M --hardware "$HW" --max-tokens 256 --prompt-file "$PFILE" --out "$OUT/lmx_$ARM.json" --quiet "$@" > "$OUT/lmx_$ARM.stdout" 2>&1
rc=$?
summ=$($PY - "$OUT/lmx_$ARM.json" "$OUT/capture_$ARM.jsonl" <<'EOF'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print("no json", e); sys.exit()
caps = [json.loads(l) for l in open(sys.argv[2])] if sys.argv[2] else []
print({k: d.get(k) for k in ("tokSOut", "ttftMs", "promptTokens", "outputTokens")}, "samples:", [s.get("tokSOut") for s in d.get("samples", [])],
      "| content chars:", [len(c["text"]) for c in caps[1:]], "| head:", repr(caps[-1]["text"][:50]) if caps else "")
EOF
)
log "$ARM: lmx rc=$rc $summ"
