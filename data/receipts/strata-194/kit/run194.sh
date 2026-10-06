#!/usr/bin/env bash
# PREREG_STRATA_194 runner (runs ON .194). usage: run194.sh strata|llama ARM PROMPT_FILE "<llama-server flags>" [lmx extra...]
# Fresh server per arm (PID recorded, killed by PID) -> gates -> g4_proxy capture -> lmx (1 warmup + 3 timed) with an
# nvidia-smi clock sampler running alongside.
set -uo pipefail
K="$(cd "$(dirname "$0")" && pwd)"; OUT="$K/runs"; mkdir -p "$OUT"; LOG="$OUT/run.log"
ENGINE=$1; ARM=$2; PF=$3; FLAGS=${4:-}; shift 4
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
if [ "$ENGINE" = strata ]; then
  CFG=${STRATA_CFG:?}; PORT=8080
  echo '{"reasoning_effort": "none"}' > "${CFG%.json}.shared-settings.json"
  (cd ~/strata && exec ~/strata/.venv/bin/python serve/server.py --engine strata --config "$CFG" --port $PORT) > "$OUT/server_$ARM.log" 2>&1 &
  HFID=${HFID:-ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF}; ENAME=custom
else
  PORT=8095; M=${LLAMA_MODEL:-$HOME/AI/Models/fn_gsq_base/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf}
  GGML_CUDA_ALLREDUCE=internal ${LLAMA_BIN:-$HOME/buun-0b278/build_sm60/bin/llama-server} -m $M -c 8192 -np 1 -ctk f16 -ctv f16 --reasoning off --jinja \
    --host 127.0.0.1 --port $PORT $FLAGS > "$OUT/server_$ARM.log" 2>&1 &
  HFID=${HFID:-ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF}; ENAME=llama.cpp
fi
SP=$!; echo $SP > "$OUT/server.pid"
cleanup() { kill ${PP:-} ${CP:-} 2>/dev/null; kill $SP 2>/dev/null; for i in $(seq 1 90); do kill -0 $SP 2>/dev/null || break; sleep 1; done; }
trap cleanup EXIT
t0=$(date +%s); up=0
for i in $(seq 1 1200); do
  kill -0 $SP 2>/dev/null || break
  h=$(curl -s -m 2 http://127.0.0.1:$PORT/health)
  if [ "$ENGINE" = strata ]; then case "$h" in *'"loaded": true'*|*'"loaded":true'*) up=1; break;; esac
  else curl -sf -m 2 http://127.0.0.1:$PORT/health >/dev/null && { up=1; break; }; fi
  sleep 1
done
[ $up = 1 ] || { log "$ARM: not up after $(( $(date +%s) - t0 ))s: $(grep -i -E 'error|fail|out of memory' "$OUT/server_$ARM.log" | tail -2 | tr '\n' ' ' | cut -c1-300)"; exit 1; }
log "$ARM: up in $(( $(date +%s) - t0 ))s; engine $ENGINE; flags [$FLAGS]; RAM $(free -g | awk '/^Mem:/{print "used "$3" avail "$7}') GB; VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' ' ')MiB"
python3 "$K/g4_proxy.py" 8097 $PORT "$OUT/capture_$ARM.jsonl" & PP=$!
for i in $(seq 1 20); do curl -sf -m 2 http://127.0.0.1:8097/health >/dev/null && break; sleep 0.5; done
nvidia-smi --query-gpu=timestamp,index,clocks.sm,utilization.gpu,power.draw --format=csv,noheader -lms 1000 > "$OUT/clocks_$ARM.csv" & CP=$!
"$K/lmx" speed-test run $ENAME --mode remote --base-url http://127.0.0.1:8097 --hf-id $HFID --quantization ${QUANT:-IQ3_XXS} \
  --hardware "$K/hw_194.json" --max-tokens 256 --prompt-file "$PF" --out "$OUT/lmx_$ARM.json" --quiet "$@" > "$OUT/lmx_$ARM.stdout" 2>&1
rc=$?
summ=$(python3 - "$OUT/lmx_$ARM.json" "$OUT/capture_$ARM.jsonl" "$OUT/clocks_$ARM.csv" <<'PY'
import json, sys, statistics
try: d = json.load(open(sys.argv[1]))
except Exception as e: print("no json", e); sys.exit()
caps = [json.loads(l) for l in open(sys.argv[2])][-4:]
st = [((c.get("timings") or {}).get("draft_n_accepted"), (c.get("timings") or {}).get("draft_n")) for c in caps[1:]]
clk = [int(l.split(",")[2].split()[0]) for l in open(sys.argv[3]) if l.count(",") >= 4 and l.split(",")[2].strip().split()[0].isdigit()]
busy = [c for c in clk if c > 500]
print({k: d.get(k) for k in ("tokSOut", "ttftMs", "promptTokens", "outputTokens")}, "samples:", [s.get("tokSOut") for s in d.get("samples", [])],
      "| acc/drafted:", st, "| content chars:", [len(c["text"]) for c in caps[1:]], "| busy SM MHz median:", statistics.median(busy) if busy else None)
PY
)
log "$ARM: lmx rc=$rc $summ"
