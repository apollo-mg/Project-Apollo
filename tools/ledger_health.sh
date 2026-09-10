#!/usr/bin/env bash
# Escalate a stale/failed ledger heartbeat into DRIFT_WARNING.md.
# Called from run_diagnostics.sh so it lands in the channel agents already resolve at boot.
# STALE_HOURS default 6 = two missed 3-hour runs, so a single blip does not cry wolf.
set -u
ROOT=/mnt/TG_2TB/Projects/Apollo
BEAT=$ROOT/data/dev_diaries/.ledger_heartbeat.json
DRIFT=$ROOT/DRIFT_WARNING.md
STALE_HOURS="${STALE_HOURS:-6}"
warn () { { echo; echo "## Ledger subsystem"; echo; echo "$1"; } >> "$DRIFT"; echo "❌ ledger: $1"; }

[ -f "$BEAT" ] || { warn "No ledger heartbeat at \`$BEAT\`. The periodic diary has NEVER run, or its state was deleted. Check \`tools/ledger_run.sh\` and its schedule."; exit 1; }
TS=$(grep -o '"ts":[0-9]*' "$BEAT" | cut -d: -f2)
ST=$(grep -o '"status":"[a-z]*"' "$BEAT" | cut -d'"' -f4)
RE=$(grep -o '"reason":"[^"]*"' "$BEAT" | cut -d'"' -f4)
AGE=$(( ( $(date +%s) - ${TS:-0} ) / 3600 ))
if [ "$AGE" -ge "$STALE_HOURS" ]; then
  warn "Ledger heartbeat is **${AGE}h old** (threshold ${STALE_HOURS}h). Last status \`$ST\`. The periodic diary has stopped running — it is NOT capturing session context right now."
elif [ "$ST" = "error" ]; then
  warn "Ledger last run FAILED: \`$RE\` (${AGE}h ago)."
elif [ "$ST" = "degraded" ]; then
  LASTOK=$ROOT/data/dev_diaries/.ledger_last_ok
  OKAGE=$(( ( $(date +%s) - $(cat "$LASTOK" 2>/dev/null || echo 0) ) / 3600 ))
  if [ "$OKAGE" -ge "$STALE_HOURS" ]; then
    warn "Ledger has been **degraded for ${OKAGE}h** — skeleton telemetry only, no prose. Last reason: \`$RE\`. Most likely every model endpoint is unreachable; the diary is recording WHAT happened but not WHY, which is the half that matters."
  else
    echo "⚠️  ledger: degraded (${AGE}h ago, last good ${OKAGE}h) — $RE"
  fi
else
  # A ledger that keeps reporting idle -- because a benchmark lock is held for days, or because
  # nothing is happening -- still stops producing prose. Escalate on the age of the last GOOD
  # run, not just on the current status.
  LASTOK=$ROOT/data/dev_diaries/.ledger_last_ok
  OKAGE=$(( ( $(date +%s) - $(cat "$LASTOK" 2>/dev/null || echo 0) ) / 3600 ))
  # `idle` because there were genuinely no events is the system working, not drifting. Escalating
  # it teaches agents to ignore DRIFT_WARNING.md, which is the one channel that must stay
  # trustworthy. Only escalate idle when the ledger has ALSO stopped running (caught by the AGE
  # check above) -- a quiet weekend is not drift. Observed 2026-08-30: a false alarm fired for
  # "only 1 new events since line 89320", i.e. nothing happened overnight.
  if [ "$ST" != "ok" ] && [ "$ST" != "idle" ] && [ "$OKAGE" -ge "$STALE_HOURS" ]; then
    warn "Ledger status \`$ST\` and **no successful entry for ${OKAGE}h**. Reason: \`$RE\`. It is running but not producing prose."
  else
    # Heartbeat is healthy -- now ask whether the OUTPUT is. Same check the human observer runs,
    # different sink, so neither path depends on the other noticing.
    if VMSG=$($ROOT/tools/ledger_validate.sh 2>/dev/null); then
      echo "✅ ledger: $ST, ${AGE}h ago"
    else
      warn "Ledger ran successfully but produced a MALFORMED entry: $VMSG. Check \`tools/ledger_build.py\` reasoning stripping, and fix today's entry in \`data/dev_diaries/\`."
    fi
  fi
fi
