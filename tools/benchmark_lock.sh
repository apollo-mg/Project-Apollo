#!/usr/bin/env bash
# Advisory lock so background jobs (the ledger, daydream, anything that talks to a model
# endpoint) stay off the fleet while a benchmark leg is running.
#
# WHY: the ledger's endpoint fallback ends at 127.0.0.1:8090 and it sends a ~120k-char prompt.
# On 2026-08-28 it fell through to the box running an Ornith calibration and pushed ~30k tokens
# of prefill into a 131072-context server mid-run. It did not cause that run's failure (the
# timestamps clear it -- see AFM-26) but nothing prevented it, and the same node's llama-swap
# config already carries the rule in prose: stop background traffic before an A/B leg.
#
# LIVENESS: the lock records a PID and is IGNORED if that process is gone. A benchmark that
# crashes must not disable the ledger forever -- silent permanent lockout is exactly the class
# of failure this repo keeps finding.
#
#   ./tools/benchmark_lock.sh acquire "ornith_v3 calibration"   # writes the lock
#   ./tools/benchmark_lock.sh release
#   ./tools/benchmark_lock.sh check                             # exit 0 = held, 1 = free
set -u
LOCK=/mnt/TG_2TB/Projects/Apollo/run/benchmark.lock
mkdir -p "$(dirname "$LOCK")"

case "${1:-check}" in
  acquire)
    # Record the CALLER's pid ($PPID), not this script's ($$). This script exits immediately,
    # so recording $$ makes the lock instantly stale and it is ignored -- which is exactly what
    # happened the first time this was tested. Third arg overrides for odd invocations.
    HOLDER="${3:-$PPID}"
    printf '%s\t%s\t%s\n' "$HOLDER" "$(date -Iseconds)" "${2:-unnamed benchmark}" > "$LOCK"
    echo "benchmark lock acquired by pid $HOLDER: ${2:-unnamed benchmark}"
    ;;
  release)
    rm -f "$LOCK"; echo "benchmark lock released"
    ;;
  check|status)
    [ -f "$LOCK" ] || exit 1
    PID=$(cut -f1 "$LOCK"); ISO=$(cut -f2 "$LOCK"); WHAT=$(cut -f3 "$LOCK")
    if ! kill -0 "$PID" 2>/dev/null; then
      # stale: holder is gone. Clear it rather than blocking indefinitely.
      rm -f "$LOCK"; echo "stale lock from dead pid $PID cleared" >&2; exit 1
    fi
    AGE=$(( ( $(date +%s) - $(date -d "$ISO" +%s) ) / 60 ))
    echo "held by pid $PID for ${AGE}m: $WHAT"
    exit 0
    ;;
  *) echo "usage: $0 {acquire <desc>|release|check}" >&2; exit 2 ;;
esac
