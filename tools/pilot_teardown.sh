#!/usr/bin/env bash
# Tear down a finished .194 pilot: stop the arm servers, release the lock, power the NODE off.
#
# WHY THIS EXISTS. On 2026-09-22 a pilot's completion waiter killed both llama-server
# processes, confirmed all four GPUs at 0 MiB, released the benchmark lock, exited 0 -- and
# reported "shut down cleanly". The NODE stayed up for seven hours at ~218 W idle until Mark
# noticed it at 4am and powered it off by hand.
#
# The automation did exactly what it was written to do. The bug was the SPEC, and underneath
# that a bad probe: `nvidia-smi` reading 0 MiB proves the servers stopped and says nothing
# about whether the box is on. It cannot distinguish the state we wanted from a lesser one,
# which is [[readiness-probes-lie]] pointed at teardown instead of startup. The probe that
# cannot pass while the node is up is `s194.sh status` reporting `chassis : off`.
#
#   pilot_teardown.sh            stop servers, release lock, leave the node UP
#   pilot_teardown.sh --poweroff stop servers, release lock, power the node OFF
set -u
ROOT=/mnt/TG_2TB/Projects/Apollo
HOST=10.0.0.194
POWEROFF=0
[ "${1:-}" = "--poweroff" ] && POWEROFF=1

echo "== stopping arm servers on $HOST =="
ssh -o ConnectTimeout=8 "$HOST" '
  for p in ~/argus_q6k.pid ~/argus_iq3s.pid; do
      [ -f "$p" ] && { kill "$(cat "$p")" 2>/dev/null; rm -f "$p"; }
  done
  sleep 6
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader' 2>&1 || echo "  (host unreachable -- already down?)"

echo "== releasing benchmark lock =="
"$ROOT/tools/benchmark_lock.sh" release 2>&1 | tail -1

if [ "$POWEROFF" = 1 ]; then
    echo "== powering off the node =="
    # s194.sh refuses while llama-server is running, which is the guard we want: if the kill
    # above failed, this stops rather than yanking a live job.
    "$ROOT/tools/s194.sh" off
    echo "== verifying with a probe that cannot pass while the node is up =="
    sleep 5
    "$ROOT/tools/s194.sh" status | sed 's/^/  /'
else
    echo "== node left UP (pass --poweroff to shut it down) =="
fi
