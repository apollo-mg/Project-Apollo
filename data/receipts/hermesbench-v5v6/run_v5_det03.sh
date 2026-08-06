#!/usr/bin/env bash
# HermesBench V5 replicate under the PINNED serving config (bench_server.sh v5).
#
# Purpose: hermes01 and v5_det02 differ in split mode AND draw, so the 4 tasks that moved
# between them cannot be attributed. This is the first same-config V5 replicate, and it is
# the only missing piece needed to decide whether v6_det01's 56-vs-55 margin is real.
#
# Pre-registration + decision rule: data/receipts/hermesbench-v5v6/PREDICTIONS_v5_replicate.md
#
# Flags matched exactly to v5_det02 / v6_det01 so the ONLY variable is the draw.
# --timeout-overhead 300: P100 prefill ~148 tok/s, 29 tool schemas push turn 1 to ~13k
#   tokens (~83 s) before the first output token. Defaults produce INFRA_ERRORs that read
#   as model failures.
# Explicit --model/--base-url, never --use-hermes-config: that flag resolves to
#   grok-composer-2.5-fast, a PAID CLOUD endpoint, despite the local config pointing at .73.
set -u
cd /home/mark/projects/hermes-bench-tool-call
RUN=v5_det03
LOG=/home/mark/projects/hermes-bench-tool-call/${RUN}.log

SERVING=$(ssh -o BatchMode=yes -o ConnectTimeout=8 mark@10.0.0.73 \
	'python3 -c "import json;d=json.load(open(\"/home/mark/bench-stack/serving_config_v5.json\"));print(d[\"version\"],d[\"pid\"],d[\"model_path\"])"' 2>/dev/null)
echo "=== $(date -Is) START $RUN ===" >> "$LOG"
echo "=== serving: ${SERVING:-UNKNOWN} ===" >> "$LOG"
case "$SERVING" in
	v5\ *) : ;;
	*) echo "=== ABORT: .73 is not serving v5 (got: ${SERVING:-nothing}) ===" >> "$LOG"
	   echo "=== SIGNAL: hermesbench $RUN done ===" >> "$LOG"; exit 1 ;;
esac

.venv/bin/python -m hermesbench run \
  --model "Hermes3.6-35B-A3B-Genesis-V5-APEX" \
  --base-url http://10.0.0.73:8082/v1 \
  --all --toolsets all \
  --timeout-overhead 300 \
  --run-id "$RUN" >> "$LOG" 2>&1
echo "=== $(date -Is) EXIT rc=$? ===" >> "$LOG"

# Copy out immediately -- ~/projects is not the durable location.
DEST=/mnt/TG_2TB/Projects/Apollo/data/receipts/hermesbench-v5v6
mkdir -p "$DEST"
cp -a "results/$RUN" "$DEST/" 2>/dev/null
cp -a "$LOG" "$DEST/" 2>/dev/null
echo "=== SIGNAL: hermesbench $RUN done ===" >> "$LOG"
