#!/bin/bash
# PREREG_ABSTENTIONBENCH Addendum 2: Qwen3.8-27B (the .73 daily driver, via the wake proxy) thinking OFF vs ON, interleaved
# pairs until all 2,004 are done or the deadline; then both arms judged (norefs, exact) on the 9070 with Clef paused, and the
# paired comparison under each judge. Launch with systemd-run --user and ExecStopPost restoring Clef.
set -u
R=/mnt/TG_2TB/Projects/Apollo; D=$R/data/receipts/abstentionbench; CK=/mnt/TG_2TB/toolchains/AbstentionBench
PY=/mnt/TG_2TB/toolchains/abench-venv/bin/python; LOG=$D/raw/q27_state.log
log () { echo "$(date '+%F %T') $*" >> $LOG; }
log "chain start"
$PY -s $D/run_q27_pairs.py --items $CK/fast_subset.jsonl --off $D/raw/Q27OFF.jsonl --on $D/raw/Q27ON.jsonl --proxy http://127.0.0.1:8099 \
  --node http://10.0.0.73:8080 --deadline 2026-10-26T12:00 --expect-model Qwen3.8-27B-Q6_K.gguf >> $LOG 2>&1
log "subject rc=$? off=$(grep -vc '"error"' $D/raw/Q27OFF.jsonl) on=$(grep -vc '"error"' $D/raw/Q27ON.jsonl) errors_off=$(grep -c '"error"' $D/raw/Q27OFF.jsonl) errors_on=$(grep -c '"error"' $D/raw/Q27ON.jsonl)"
bash $D/run_chain_judge.sh Q27OFF Q27ON; log "judge chain rc=$?"
for V in norefs exact; do $PY -s $D/compare_arms.py --checkout $CK --a Q27OFF --b Q27ON --judge $V >> $LOG 2>&1; log "compare $V rc=$?"; done
log "DONE"
