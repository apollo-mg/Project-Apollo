#!/usr/bin/env bash
# PREREG_STRATA_9070_Q36.md runner. usage: run_q36.sh strata ARM PROMPT_FILE | run_q36.sh llama ARM PROMPT_FILE NCMOE
# Fresh server per arm (PID recorded, killed by PID) -> loaded/health -> capture proxy -> lmx custom remote
# (1 warm-up + 3 timed, median), the same client for both engines.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; OUT="$HERE/runs"; mkdir -p "$OUT"; LOG="$OUT/run.log"
ST=/mnt/TG_2TB/Projects/strata; PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
G4="$HERE/../../gemma4-9070-spec"; PROXY="$G4/g4_proxy.py"; HW="$G4/hw_9070xt.json"
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_upstream_f74e2fa/build_rocm/bin/llama-server
MODEL=/mnt/TG_2TB/AI/Models/Qwen3.6-35B-A3B-base-GGUF/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
CFG=$ST/strata-qwen36-ud-q4_k_xl-nomtp.json
ENG=$1; ARM=$2; PFILE=$3; K=${4:-}
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
if [ "$ENG" = strata ]; then
  echo '{"reasoning_effort": "none"}' > "${CFG%.json}.shared-settings.json"
  (cd "$ST" && exec "$ST/.venv/bin/python" serve/server.py --engine strata --config "$CFG" --port 8080) > "$OUT/server_$ARM.log" 2>&1 &
  SP=$!; PORT=8080
else
  "$BIN" -m "$MODEL" -ngl 99 -fa on -c 32768 -ctk f16 -ctv f16 -np 1 -t 8 -fit off --n-cpu-moe "$K" \
    --chat-template-kwargs '{"enable_thinking":false}' --host 127.0.0.1 --port 8095 > "$OUT/server_$ARM.log" 2>&1 < /dev/null &
  SP=$!; PORT=8095
fi
echo $SP > "$OUT/server.pid"
cleanup() { kill ${PP:-} 2>/dev/null; kill $SP 2>/dev/null; for i in $(seq 1 60); do kill -0 $SP 2>/dev/null || break; sleep 1; done; }
trap cleanup EXIT
t0=$(date +%s); up=0
for i in $(seq 1 900); do
  kill -0 $SP 2>/dev/null || break
  h=$(curl -s -m 2 http://127.0.0.1:$PORT/health)
  case "$h" in *'"loaded": true'*|*'"loaded":true'*) up=1; break;; esac
  [ "$ENG" = llama ] && case "$h" in *'"ok"'*) up=1; break;; esac
  sleep 1
done
[ $up = 1 ] || { log "$ARM: not up after $(( $(date +%s) - t0 ))s: $(grep -iE 'error|fail|out of memory' "$OUT/server_$ARM.log" | tail -2 | tr '\n' ' ' | cut -c1-300)"; exit 1; }
ram=$(free -g | awk '/^Mem:/{print "used "$3" avail "$7" GB"}'); vram=$(rocm-smi --showmeminfo vram 2>/dev/null | awk -F': ' '/Total Used/{printf "%.2f", $NF/1e9}')
log "$ARM: up in $(( $(date +%s) - t0 ))s; RAM $ram; VRAM used $vram GB; ${K:+ncmoe $K}"
$PY "$PROXY" 8097 $PORT "$OUT/capture_$ARM.jsonl" & PP=$!
for i in $(seq 1 20); do curl -sf -m 2 http://127.0.0.1:8097/health >/dev/null && break; sleep 0.5; done
lmx speed-test run custom --mode remote --base-url http://127.0.0.1:8097 --hf-id unsloth/Qwen3.6-35B-A3B-GGUF \
  --quantization UD-Q4_K_XL --hardware "$HW" --max-tokens 256 --prompt-file "$PFILE" --out "$OUT/lmx_$ARM.json" --quiet > "$OUT/lmx_$ARM.stdout" 2>&1
rc=$?
summ=$($PY - "$OUT/lmx_$ARM.json" "$OUT/capture_$ARM.jsonl" <<'PYEOF'
import json, sys
try: d = json.load(open(sys.argv[1]))
except Exception as e: print("no json", e); sys.exit()
caps = [json.loads(l) for l in open(sys.argv[2])] if sys.argv[2] else []
print({k: d.get(k) for k in ("tokSOut", "ttftMs", "promptTokens", "outputTokens")}, "samples:", [s.get("tokSOut") for s in d.get("samples", [])],
      "| content chars:", [len(c.get("text", "")) for c in caps[1:]], "| head:", repr(caps[-1].get("text", "")[:60]) if caps else "")
PYEOF
)
log "$ARM: lmx rc=$rc $summ"
