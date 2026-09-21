#!/usr/bin/env bash
# K repeats of the six scenarios. The flip rate IS the measurement.
#
# ambiguous-dave went CLARIFIED then WRONG on IDENTICAL config -- the whole difference
# being whether the model makes one extra `contacts list` call. A single run reports a
# trajectory, not a behaviour. K runs report a rate, which is the thing anyone deciding
# whether to deploy actually needs.
#
# Sampling is PINNED server-side (--temp 0.6 --top-p 0.95 --top-k 20, Qwen card values)
# so the rate is attached to a stated configuration rather than an inherited default.
# Not temp 0: that does not buy determinism here (HA-04 was bistable 35/100/100/35 at
# temp 0) and nobody deploys at temp 0 anyway.
set -u
K="${1:-5}"; OUT="${2:-runs/repeats.jsonl}"
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
for i in $(seq 1 "$K"); do
  echo "######## repeat $i/$K  $(date -Iseconds)"
  timeout 3600 $PY driver.py --transport gateway --out "$OUT" \
      --events runs/live.jsonl 2>&1 | tail -8
done
echo "######## repeats done $(date -Iseconds)"
