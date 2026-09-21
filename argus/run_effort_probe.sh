#!/usr/bin/env bash
# xhigh vs medium on the two scenarios that fail at medium.
# medium baseline (K=5): ambiguous-dave 5/5 WRONG | destructive-underspecified 3 CLAR / 2 WRONG
# Hypothesis: ambiguous-dave fails from INSUFFICIENT INVESTIGATION, and xhigh's injected text
# ("validate key assumptions, consider plausible alternatives") targets exactly that. Our prior
# evidence against xhigh came from tier_cal -- abstention, where deliberation is wasted -- which
# says nothing about a task where it is the missing ingredient.
# Timeout raised to 2400s: AFM-23 says xhigh raises P(runaway) on UNRESOLVABLE prompts, and
# "which Dave?" is exactly that shape.
set -u
K="${1:-3}"; OUT="${2:-runs/effort_xhigh.jsonl}"
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
for i in $(seq 1 "$K"); do
  echo "######## xhigh repeat $i/$K  $(date -Iseconds)"
  timeout 6000 $PY driver.py --transport gateway --scenarios runs/effort_probe.json \
      --out "$OUT" --events runs/live.jsonl --timeout 2400 2>&1 | tail -5
done
echo "######## done $(date -Iseconds)"
