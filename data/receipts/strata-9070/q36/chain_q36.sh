#!/usr/bin/env bash
# PREREG_STRATA_9070_Q36.md, launch 3 (Addendum 2). Launch with:
#   systemd-run --user --unit=strata-q36 --collect -p MemoryMax=26G -p ExecStopPost="systemctl --user start apollo-clef.service apollo-clef-monitor.service" bash chain_q36.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; OUT="$HERE/runs"; mkdir -p "$OUT"; LOG="$OUT/run.log"
P="$HERE/../../gemma4-9070-spec"; CODE="$P/canonical_code-v1.txt"; REASON="$P/canonical_reasoning-v1.txt"
MTPCFG=/mnt/TG_2TB/Projects/strata/strata-qwen36-ud-q4_k_xl.json
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
med() { python3 -c "
import json,sys,statistics as st
s=[]
for f in sys.argv[1:]:
  try: s+=[x['tokSOut'] for x in json.load(open(f)).get('samples',[]) if x.get('tokSOut') is not None]
  except Exception: pass
print(st.median(s) if s else 0)" "$OUT/lmx_$1_a.json" "$OUT/lmx_$1_b.json"; }
vram() { grep -E "^[0-9-]+ [0-9:]+ $1: up" "$LOG" | tail -1 | grep -oE "VRAM used [0-9.]+" | grep -oE "[0-9.]+$"; }
log "launch 3 start (MemoryMax 26G, matched greedy, Strata --vram-reserve-mib 1024); Clef stopping"
systemctl --user stop apollo-clef-monitor.service apollo-clef.service; sleep 3
bash "$HERE/run_q36.sh" strata S_code "$CODE"
SV=$(vram S_code); [ -n "$SV" ] || { log "ABORT: S_code did not report VRAM"; exit 1; }
budget=$(python3 -c "print(round(float('$SV') + 0.10, 2))"); log "matched VRAM budget: <= $budget GB (Strata $SV + 0.10)"
best=""; bv=0
for K in 16 18 20; do
  bash "$HERE/run_q36.sh" llama L_code_k$K "$CODE" $K
  v=$(med L_code_k$K); kv=$(vram L_code_k$K)
  if [ -n "$kv" ] && python3 -c "import sys; sys.exit(0 if float('$kv') <= $budget and float('$v') > float('$bv') else 1)"; then best=$K; bv=$v; fi
done
[ -n "$best" ] || { best=20; log "no split met the VRAM budget; using 20"; }
log "llama primary split: ncmoe $best ($bv tok/s, VRAM $(vram L_code_k$best) GB)"
STRATA_CFG=$MTPCFG bash "$HERE/run_q36.sh" strata S_mtp_code "$CODE"
bash "$HERE/run_q36.sh" llama L_mtp_code "$CODE" $best "--spec-type draft-mtp" || true
MK=$best; if ! grep -qE "L_mtp_code: lmx" "$LOG"; then MK=$((best+2)); log "L_mtp did not load at $best; using $MK"; bash "$HERE/run_q36.sh" llama L_mtp_code_k$MK "$CODE" $MK "--spec-type draft-mtp"; fi
bash "$HERE/run_q36.sh" strata S_reason "$REASON"
bash "$HERE/run_q36.sh" llama L_reason "$REASON" $best
STRATA_CFG=$MTPCFG bash "$HERE/run_q36.sh" strata S_mtp_reason "$REASON"
bash "$HERE/run_q36.sh" llama L_mtp_reason "$REASON" $MK "--spec-type draft-mtp"
log "strata cache: $(grep -hE 'hybrid experts: [0-9]+ of [0-9]+ batch entries' /mnt/TG_2TB/Projects/strata/strata-qwen36-ud-q4_k_xl*.log | tail -4 | tr '\n' ';')"
log "strata drafts: $(grep -hoE 'drafts accepted [0-9]+ of [0-9]+' /mnt/TG_2TB/Projects/strata/strata-qwen36-ud-q4_k_xl.log | tail -4 | tr '\n' ';')"
log "unit memory peak: $(cat /sys/fs/cgroup$(systemctl --user show -p ControlGroup --value strata-q36)/memory.peak 2>/dev/null)"
log "DONE"
