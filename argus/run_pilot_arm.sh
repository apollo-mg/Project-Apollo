#!/usr/bin/env bash
# One argus pilot arm. $1=label $2=fixture  (each arm needs its OWN fixture and
# sandbox: fake-google/state.json is a single file and two arms sharing it corrupt
# each other's audit log, which is how an arm silently measures the other's actions.)
set -u
L="$1"; FX="$2"
A=/mnt/TG_2TB/Projects/Apollo/argus
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
cd "$A"
# -u: without it Python block-buffers stdout when it is a file rather than a tty, so the
# per-scenario progress lines sit unflushed and an arm that is working looks hung. The
# JSONL sink is explicitly flushed+fsynced per row, so the DATA was never at risk -- but
# judging progress from the console log was, and did, mislead.
exec timeout 14400 "$PY" -u driver.py \
    --hermes-home "$A/fixtures/$FX/agent-home" \
    --fake-root  "$A/fixtures/$FX/fake-google" \
    --sandbox    "$A/runs/sandbox${L}" \
    --scenarios  "$A/families_v4.json" \
    --out        "$A/runs/pilot4/${L}.jsonl" \
    --events     "" \
    --timeout    900 \
    --agent-stderr "$A/runs/pilot4/${L}_agent.log" \
    --agent-cmd "$PY" -m acp_adapter.entry
