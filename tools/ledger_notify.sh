#!/usr/bin/env bash
# HUMAN-facing ledger alarm. Second, INDEPENDENT observer alongside ledger_health.sh.
#
# WHY TWO: ledger_health.sh routes into DRIFT_WARNING.md, which reaches AGENTS -- but only if
# something reads it. That channel was already proven fragile: run_diagnostics.sh is launched
# from apollo-ctl.sh, apollo-ctl has not run since 2026-07-06 (run/*.log mtimes), so a drift
# warning sat unresolved for eight weeks and nobody saw it. A single observer that depends on
# another unmonitored system is not an observer.
#
# INDEPENDENCE is the point. This path shares NOTHING with the agent path:
#   agent path : cron -> run_diagnostics.sh -> DRIFT_WARNING.md -> agent reads at session start
#   human path : cron -> this script        -> desktop notification + terminal MOTD
# Different trigger, different sink, different reader. Either can die without silencing the other.
set -u
ROOT=/mnt/TG_2TB/Projects/Apollo
BEAT=$ROOT/data/dev_diaries/.ledger_heartbeat.json
MOTD=$ROOT/data/dev_diaries/.ledger_motd
STALE_HOURS="${STALE_HOURS:-6}"

msg=""
if [ ! -f "$BEAT" ]; then
  msg="Apollo ledger has NEVER run (no heartbeat)."
else
  TS=$(grep -o '"ts":[0-9]*' "$BEAT" | cut -d: -f2)
  ST=$(grep -o '"status":"[a-z]*"' "$BEAT" | cut -d'"' -f4)
  RE=$(grep -o '"reason":"[^"]*"' "$BEAT" | cut -d'"' -f4)
  AGE=$(( ( $(date +%s) - ${TS:-0} ) / 3600 ))
  [ "$AGE" -ge "$STALE_HOURS" ] && msg="Apollo ledger stale: ${AGE}h since last run (last status: $ST)."
  [ "$ST" = "error" ]           && msg="Apollo ledger FAILED: $RE"
  if [ "$ST" = "degraded" ]; then
    OKAGE=$(( ( $(date +%s) - $(cat "$ROOT/data/dev_diaries/.ledger_last_ok" 2>/dev/null || echo 0) ) / 3600 ))
    [ "$OKAGE" -ge 12 ] && msg="Apollo ledger degraded ${OKAGE}h — no model reachable, skeleton only"
  fi
fi

# Liveness is not validity. A run can report ok and still write an unusable entry -- that is
# exactly what happened on 2026-08-30. Only checked when the heartbeat itself is clean, so a
# real outage still reports as an outage rather than as a formatting complaint.
if [ -z "$msg" ]; then
  if VMSG=$($ROOT/tools/ledger_validate.sh 2>/dev/null); then :; else
    [ -n "$VMSG" ] && msg="Apollo ledger wrote a BAD entry: $VMSG"
  fi
fi

if [ -n "$msg" ]; then
  printf '\033[1;33m⚠  %s\033[0m\n  fix: %s/tools/ledger_run.sh   check: %s/tools/ledger_health.sh\n' \
      "$msg" "$ROOT" "$ROOT" > "$MOTD"
  command -v notify-send >/dev/null 2>&1 && \
      DISPLAY="${DISPLAY:-:0}" notify-send -u critical "Apollo ledger" "$msg" 2>/dev/null
  echo "ALERT: $msg"
else
  : > "$MOTD"
  echo "ok"
fi
