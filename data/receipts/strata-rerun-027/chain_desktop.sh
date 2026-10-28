#!/usr/bin/env bash
# PREREG_STRATA_RERUN_027.md, desktop arms. Launch with:
#   systemd-run --user --unit=strata-rerun --collect -p MemoryMax=26G -p ExecStopPost="systemctl --user start apollo-clef.service apollo-clef-monitor.service" bash chain_desktop.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; LOG="$HERE/runs/run.log"; mkdir -p "$HERE/runs"
P="$HERE/../gemma4-9070-spec"
export STRATA_CFG=/mnt/TG_2TB/Projects/strata/strata-coder-iq1_m.json HFID=ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF QUANT=IQ1_M
echo "$(date '+%F %T') desktop rerun start (v0.2.7, Coder IQ1_M, MemoryMax 26G); Clef stopping" | tee -a "$LOG"
systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
bash "$HERE/run_rerun.sh" strata D_code_r1 "$P/canonical_code-v1.txt"
bash "$HERE/run_rerun.sh" strata D_code_r2 "$P/canonical_code-v1.txt"
bash "$HERE/run_rerun.sh" strata D_reason "$P/canonical_reasoning-v1.txt"
echo "$(date '+%F %T') drafts: $(grep -hoE 'drafts accepted [0-9]+ of [0-9]+' /mnt/TG_2TB/Projects/strata/strata-coder-iq1_m.log | tail -9 | tr '\n' ';')" | tee -a "$LOG"
echo "$(date '+%F %T') DONE" | tee -a "$LOG"
