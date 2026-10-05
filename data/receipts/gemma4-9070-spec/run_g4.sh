#!/usr/bin/env bash
# PREREG_GEMMA4_9070_SPEED.md runner. usage: run_g4.sh ARM_NAME "<extra llama-server flags>" [lmx extra flags...]
# One arm = fresh llama-server (PID recorded, killed by PID) -> gates -> lmx remote speed test (1 warmup + 3 timed, median).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; OUT="$HERE/runs"; mkdir -p "$OUT"; LOG="$OUT/run.log"
BIN=${BIN:-/mnt/TG_2TB/Projects/llama-master-hip/build_rocm/bin/llama-server}
LMX=${LMX:-/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/lmx}
MODEL=${MODEL:-/mnt/TG_2TB/AI/Models/gemma4/gemma-4-12b-it-Q4_K_M.gguf}
HFID=${HFID:-unsloth/gemma-4-12b-it-GGUF}; QUANT=${QUANT:-Q4_K_M}; CTX=${CTX:-262144}; N=${N:-512}; PORT=8095
ARM=$1; EXTRA=$2; shift 2
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
SLOG="$OUT/server_$ARM.log"
"$BIN" -m "$MODEL" -ngl 99 -fit off -fa on -np 1 -c "$CTX" -ctk f16 -ctv f16 --host 127.0.0.1 --port $PORT $EXTRA > "$SLOG" 2>&1 &
SP=$!; echo $SP > "$OUT/server.pid"
trap 'kill $SP 2>/dev/null; for i in $(seq 1 30); do kill -0 $SP 2>/dev/null || break; sleep 1; done' EXIT
up=0; for i in $(seq 1 240); do kill -0 $SP 2>/dev/null || break; curl -sf -m 2 http://127.0.0.1:$PORT/health >/dev/null && { up=1; break; }; sleep 1; done
[ $up = 1 ] || { log "$ARM: server not healthy: $(grep -i -E 'error|fail|out of memory' "$SLOG" | tail -3)"; exit 1; }
vram=$(rocm-smi --showmeminfo vram 2>/dev/null | awk -F': ' '/Total Used/{printf "%.2f", $NF/1e9}')
clk=$(rocm-smi --showclocks 2>/dev/null | grep -E 'sclk|mclk' | sed 's/.*: //' | tr '\n' ' ')
log "$ARM: up; flags [$EXTRA]; ctx $CTX; VRAM used $vram GB; clocks $clk"
# Deviation 2: PFILE=<canonical prompt file> replaces --prompt-tokens; PROXY=1 routes lmx through g4_proxy.py (capture only).
LPORT=$PORT; PSRC=(--prompt-tokens "$N"); [ -n "${PFILE:-}" ] && PSRC=(--prompt-file "$PFILE")
if [ "${PROXY:-0}" = 1 ]; then
  /mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3 "$HERE/g4_proxy.py" 8097 $PORT "$OUT/capture_$ARM.jsonl" & PP=$!
  trap 'kill $PP 2>/dev/null; kill $SP 2>/dev/null; for i in $(seq 1 30); do kill -0 $SP 2>/dev/null || break; sleep 1; done' EXIT
  for i in $(seq 1 20); do curl -sf -m 2 http://127.0.0.1:8097/health >/dev/null && break; sleep 0.5; done; LPORT=8097
fi
"$LMX" speed-test run llama.cpp --mode remote --base-url http://127.0.0.1:$LPORT --hf-id "$HFID" --quantization "$QUANT" \
  --hardware "$HERE/hw_9070xt.json" --max-tokens 256 "${PSRC[@]}" --out "$OUT/lmx_$ARM.json" --quiet "$@" > "$OUT/lmx_$ARM.stdout" 2>&1
rc=$?
summ=$(/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3 - "$OUT/lmx_$ARM.json" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("no json", e); sys.exit()
def find(o,k):
    if isinstance(o,dict):
        if k in o: return o[k]
        for v in o.values():
            r=find(v,k)
            if r is not None: return r
    if isinstance(o,list):
        for v in o:
            r=find(v,k)
            if r is not None: return r
m={k:find(d,k) for k in ("tokSOut","prefillTokS","ttftMs","inputTokens","promptTokens","outputTokens","completionTokens")}
s=find(d,"samples")
print({k:v for k,v in m.items() if v is not None}, "samples:", [x.get("tokSOut") for x in s] if isinstance(s,list) else s)
PY
)
acc=$(grep -E 'draft acceptance|accepted' "$SLOG" | tail -4 | sed 's/^.*slot//' | tr '\n' '|' | cut -c1-400)
log "$ARM: lmx rc=$rc $summ"
log "$ARM: draft: ${acc:-none}"
