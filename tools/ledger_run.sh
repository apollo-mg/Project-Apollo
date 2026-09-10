#!/usr/bin/env bash
# Scheduled ledger run. Extract new transcript events -> build a diary entry -> heartbeat.
#
# DESIGN CENTRE: the ABSENCE of a signal must itself be a signal. A log that stops being
# written is invisible; you find out days later when you need it. So every run writes a
# heartbeat with an explicit status, and ledger_health.sh escalates a stale or failed
# heartbeat into DRIFT_WARNING.md -- the channel agents already must resolve at session start.
#
# Failure modes this handles explicitly:
#   * session id changes         -> always picks the MOST RECENTLY MODIFIED transcript
#   * no new events since last   -> status=idle (legitimate, not a failure)
#   * model endpoint busy/down   -> status=degraded, skeleton still written
#   * anything else              -> status=error with the reason recorded
set -u
ROOT=/mnt/TG_2TB/Projects/Apollo
PY=$ROOT/venv_cachyos/bin/python3
PROJ=/home/mark/.claude/projects/-mnt-TG-2TB-Projects-Apollo
STATE=$ROOT/data/dev_diaries/.ledger_state.json
BEAT=$ROOT/data/dev_diaries/.ledger_heartbeat.json
BEATLOG=$ROOT/data/dev_diaries/.ledger_beats.jsonl
# Pass --out explicitly: ledger_build.py otherwise defaults to a HARDCODED absolute
# path, so redirecting ROOT does not redirect the output. A test run against a copy
# silently appended a section to the live diary before this was fixed.
DIARY=$ROOT/data/dev_diaries/$(date +%Y-%m-%d)_ledger.md
LASTOK=$ROOT/data/dev_diaries/.ledger_last_ok
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
LASTFAIL=""
# Endpoint order WAS a cost order (cheap already-running fleet servers first, wake proxy last).
# INVERTED 2026-08-30, deliberately, in favour of correctness.
#
# Why: .194 is the experiment box, and whatever model is loaded there is frequently one we are
# actively breaking -- a broken model answers /health with 200 exactly like a good one. On
# 2026-08-28 that produced FIVE ledger entries of pure `////////`, every one recorded as ok.
# .73 runs a known-good pinned model behind the wake proxy, so it is the only endpoint whose
# OUTPUT is predictable, and that now outranks the cost of waking it.
#
# .194 stays as a fallback, not a preference: reached only if the proxy is unreachable, and
# ledger_build.py now REJECTS a malformed entry (exit 2) so a bad model there falls through
# instead of being written. Endpoint choice and output validity are separate defences on purpose.
#
# Cost of the inversion is bounded by the idle gate above: a run with <25 new events exits before
# touching any host, so a quiet night wakes nothing. Measured 2026-08-30: .73 slept 17h26m
# straight with this fallback already wired in.
#
# The .73 entry MUST be the proxy (:8099) and never .73:8080 direct. The proxy tracks in-flight
# requests to decide when to suspend; a request that bypasses it is invisible, so .73 could
# suspend mid-generation. Going through the proxy also survives the node being asleep --
# ledger_build.py already allows timeout=1800 s, far above the ~97 s cold start.
#
# 127.0.0.1:8090 was dropped 2026-08-29: it was a transient Ornith calibration server, not a
# durable endpoint, and its absence is what put the ledger into degraded.
HOSTS="${LEDGER_HOSTS:-http://127.0.0.1:8099 http://10.0.0.194:8086 http://10.0.0.194:8084}"

# The heartbeat file is a single OVERWRITTEN snapshot, so it answers "how is it now" and
# nothing else. On 2026-08-30 that was not enough: the user journal here retains ~40 minutes,
# so there was no way to show whether the five overnight cycles had fired at all -- only to
# infer it from Persistent=true and uptime. A monitor that cannot demonstrate it was monitoring
# is one bad night away from dying unnoticed, which is how data/dev_diaries/ died the first
# time. So every beat also APPENDS one line, forever.
beat () { printf '{"ts":%s,"iso":"%s","status":"%s","events":%s,"reason":"%s"}\n' \
          "$(date +%s)" "$(date -Iseconds)" "$1" "${2:-0}" "${3:-}" \
          | tee -a "$BEATLOG" > "$BEAT"; }

# Skip the cycle if a benchmark holds the lock. Checked BEFORE extraction so the offset does
# not advance -- the events are simply picked up by the next run, which is why skipping is safe.
if LOCKINFO=$($ROOT/tools/benchmark_lock.sh check 2>/dev/null); then
  beat idle 0 "benchmark lock $LOCKINFO"
  exit 0
fi

T=$(ls -t "$PROJ"/*.jsonl 2>/dev/null | head -1)
[ -n "$T" ] || { beat error 0 "no transcript found under $PROJ"; exit 1; }

SINCE=0
[ -f "$STATE" ] && SINCE=$($PY -c "import json;print(json.load(open('$STATE')).get('last_line',0))" 2>/dev/null || echo 0)

$PY $ROOT/tools/ledger_extract.py "$T" --since-line "$SINCE" --state "$STATE" > "$TMP/ev.txt" 2>"$TMP/err"
[ $? -eq 0 ] || { beat error 0 "extract failed: $(head -c 120 "$TMP/err" | tr '\n' ' ')"; exit 1; }

N=$(wc -l < "$TMP/ev.txt")
if [ "$N" -lt 25 ]; then beat idle "$N" "only $N new events since line $SINCE"; exit 0; fi

# first reachable endpoint wins; a busy fleet degrades to skeleton rather than failing
for H in $HOSTS; do
  if [ "$(curl -s -o /dev/null -w %{http_code} -m 5 "$H/health")" = "200" ]; then
    # exit 2 = endpoint answered but its entry was malformed; exit 1 = the call itself failed.
    # Either way keep going down the list rather than giving up on the cycle.
    if $PY $ROOT/tools/ledger_build.py "$TMP/ev.txt" --host "$H" --max-chars 120000 --out "$DIARY" >"$TMP/out" 2>&1; then
      # Index into Apollo's existing vector store so the diary is SEARCHABLE. An unsearchable
      # diary is one you stop reading, which is how dev_diaries died the first time.
      # Non-fatal: a ledger written but unindexed is still a ledger.
      $PY $ROOT/tools/ledger_index.py >>"$ROOT/data/dev_diaries/.ledger_cron.log" 2>&1 \
        && { beat ok "$N" "via $H"; date +%s > "$LASTOK"; } || beat degraded "$N" "written via $H but INDEXING FAILED"
      exit 0
    fi
    echo "build failed/rejected against $H: $(tail -c 200 "$TMP/out")" >&2
    LASTFAIL="$H: $(tail -c 120 "$TMP/out" | tr '\n' ' ')"
  fi
done
$PY $ROOT/tools/ledger_build.py "$TMP/ev.txt" --skeleton-only --out "$DIARY" >/dev/null 2>&1 \
  && beat degraded "$N" "no usable endpoint; skeleton only${LASTFAIL:+ (last: $LASTFAIL)}" \
  || beat error "$N" "skeleton write failed too"
