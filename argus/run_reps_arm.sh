#!/usr/bin/env bash
# One arm of a multi-rep comparison. $1=label $2=fixture $3=reps
#
# WHY REPS: RESULT_NOISE_FLOOR measured a 10.3% discordance between two runs of the
# SAME model -- identical to the rate measured between two different quants. At one
# rep this instrument cannot distinguish any pair. The power analysis on three Q6_K
# reps puts 5 reps at 78% power for a 10-point effect, and that is the knee: 12 reps
# costs 2.4x the hardware to reach 98%.
#
# Per-item pass RATES, never majority votes -- RESULT_A1_SIZING_DISCORDANCE measured
# majority voting suppressing discordance 12.5% -> 0%.
set -u
L="$1"; FX="$2"; REPS="${3:-5}"
A=/mnt/TG_2TB/Projects/Apollo/argus
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
cd "$A"
for r in $(seq 1 "$REPS"); do
    echo "######## arm $L rep $r/$REPS  $(date -Iseconds)"
    # Each rep appends; --rep stamps the row so reps stay attributable.
    timeout 14400 "$PY" -u driver.py \
        --hermes-home "$A/fixtures/$FX/agent-home" \
        --fake-root  "$A/fixtures/$FX/fake-google" \
        --sandbox    "$A/runs/sandbox${L}" \
        --scenarios  "$A/families_v4.json" \
        --out        "$A/runs/reps/${L}.jsonl" \
        --events     "" --timeout 900 --rep "$r" \
        --agent-stderr "$A/runs/reps/${L}_agent.log" \
        --agent-cmd "$PY" -m acp_adapter.entry
    echo "######## arm $L rep $r done, $(wc -l < "$A/runs/reps/${L}.jsonl") rows total"
done
