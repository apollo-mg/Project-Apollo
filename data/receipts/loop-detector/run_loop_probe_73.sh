#!/usr/bin/env bash
# Loop-detector validation on .73. Detached; survives control-plane reboots.
#
# Swaps the Coordinator for KAT-Coder Q4_K_M (lowest quant on this node, coder workload,
# most likely of the .73 models to show degeneration), collects reasoning traces on a
# deliberately mixed problem set, then RESTORES the Coordinator.
#
# Problem set is chosen to contain both classes the detector must separate:
#   HARD  32/91/132/145 — unsolved by every config in the HumanEval+ panel; these produced
#         the longest reasoning anywhere in the campaign. Wedge candidates.
#   EASY  0/10/20/30/40/50 — all passed in the 2x2. Healthy-termination controls.
# If KAT never wedges, that is itself a result (consistent with its brevity design) and the
# detector test has to wait for Laguna on .194.
set -u
HEP=/home/mark/hep
OUT=$HEP/out
LOG=$OUT/loop_probe.log
BIN=/home/mark/buun_vbr/build/bin/llama-server
KAT="/mnt/models/AI_Models/KAT-Coder-V2.5-Dev/Kwaipilot_KAT-Coder-V2.5-Dev-Q4_K_M.gguf"
EP=http://127.0.0.1:8082
mkdir -p "$OUT"

say () { echo "[$(date '+%F %T')] $*" >> "$LOG"; }
stop_srv () {
  for p in $(pgrep -f "buun_vbr/build/bin/llama-server"); do kill "$p" 2>/dev/null; done
  for i in $(seq 1 30); do pgrep -f "buun_vbr/build/bin/llama-server" >/dev/null || break; sleep 2; done
}
wait_health () { for i in $(seq 1 120); do curl -s -m 5 $EP/health 2>/dev/null | grep -q '"ok"' && return 0; sleep 10; done; return 1; }

say "=== LOOP PROBE START ==="
nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader | tr '\n' ' ' >> "$LOG"; echo >> "$LOG"

# capture the Coordinator's argv so it can be restored byte-exactly afterwards
PID=$(pgrep -f "buun_vbr/build/bin/llama-server" | head -1)
if [ -n "${PID:-}" ]; then
  tr '\0' '\n' < /proc/$PID/cmdline > $HEP/coordinator_argv.txt
  say "captured Coordinator argv ($(wc -l < $HEP/coordinator_argv.txt) args)"
fi
stop_srv
say "Coordinator stopped; loading KAT"

setsid "$BIN" -m "$KAT" -c 32768 -np 1 -ngl 999 -fit off -fa on -sm tensor -ts .85,1.15 \
  --reasoning on --reasoning-format deepseek --jinja \
  --host 0.0.0.0 --port 8082 </dev/null > "$OUT/kat_server.log" 2>&1 &
sleep 5

if wait_health; then
  curl -s -m 10 $EP/props | python3 -c "import sys,json;print('   loaded:',json.load(sys.stdin).get('model_path','?').split('/')[-1])" >> "$LOG" 2>&1
  say "running loop probe"
  LP_ENDPOINT="$EP/v1/chat/completions" \
  LP_MODEL="KAT-Coder-V2.5-Dev-Q4_K_M" LP_TAG=kat LP_K=2 LP_MAXTOK=16000 \
  LP_TEMP=0.7 LP_TOP_P=0.95 LP_TOP_K=20 \
  LP_PROBLEMS="HumanEval/32,HumanEval/91,HumanEval/132,HumanEval/145,HumanEval/0,HumanEval/10,HumanEval/20,HumanEval/30,HumanEval/40,HumanEval/50" \
  python3 "$HEP/loop_probe.py" >> "$OUT/loop_probe_kat.log" 2>&1
  say "probe exit=$?"
  tail -8 "$OUT/loop_probe_kat.log" >> "$LOG" 2>&1
else
  say "KAT server never healthy — ABORT"
fi

stop_srv
say "restoring Coordinator"
if [ -s "$HEP/coordinator_argv.txt" ]; then
  python3 - <<'PYEOF' >> "$LOG" 2>&1
import subprocess
argv = [a for a in open("/home/mark/hep/coordinator_argv.txt").read().split("\n") if a != ""]
with open("/home/mark/hep/out/coordinator_restore.log", "w") as lf:
    subprocess.Popen(argv, stdout=lf, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True)
print(f"   Coordinator relaunched with {len(argv)} args")
PYEOF
  wait_health && say "Coordinator healthy again" || say "WARNING: Coordinator did not come back"
else
  say "WARNING: no captured argv — Coordinator NOT restored"
fi
say "=== SIGNAL: loop probe done ==="
