#!/usr/bin/env bash
# Long S3 soak. The 10-second cycle proved the mechanism; this tests whether it HOLDS.
# Three things a short test cannot see:
#   1. spurious wakeups -- RTC, USB, or stray network traffic waking the box unbidden, which
#      would silently defeat the whole point. Polled throughout, not just at the ends.
#   2. NIC losing its wake state after sitting in D3 for a long time.
#   3. whether the GPUs still come back after a real cold soak rather than a warm blip.
# Writes incrementally (append+flush) so a crash here still leaves the evidence.
set -u
H=10.0.0.73; MAC=e0:d5:5e:b5:9e:b3
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
SOAK=${1:-7200}                     # seconds asleep, default 2h
LOG=$(dirname "$0")/soak_$(date +%Y%m%d_%H%M).log
say () { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }

say "PRE-FLIGHT"
ssh -n -o ConnectTimeout=10 $H 'nvidia-smi --query-gpu=index,memory.used,temperature.gpu --format=csv,noheader' \
  | sed 's/^/  gpu /' | tee -a "$LOG"
N=$(ssh -n $H 'pgrep -xc llama-server' 2>/dev/null | head -1); N=${N:-0}
[ "$N" != "0" ] && { say "ABORT: llama-server running (32 GiB VRAM spill into 24 GiB /var)"; exit 1; }
B0=$(ssh -n $H 'cat /sys/power/suspend_stats/success')
say "  suspend_stats/success before: $B0"

say "SUSPEND (soak ${SOAK}s)"
ssh -n $H 'sudo -n systemd-run --on-active=2 --timer-property=AccuracySec=100ms systemctl suspend' >/dev/null 2>&1 \
  || { say "ABORT: could not schedule suspend"; exit 1; }
DOWN=0
for i in $(seq 1 60); do ping -c1 -W1 $H >/dev/null 2>&1 || { DOWN=$(date +%s); say "  DOWN (took ${i}s)"; break; }; sleep 1; done
[ "$DOWN" = "0" ] && { say "FAIL: never went down"; exit 1; }

say "SOAKING — polling for spurious wake every 60s"
SPURIOUS=0
END=$((DOWN+SOAK))
while [ "$(date +%s)" -lt "$END" ]; do
  sleep 60
  if ping -c1 -W1 $H >/dev/null 2>&1; then
    SPURIOUS=$((SPURIOUS+1))
    say "  !! SPURIOUS WAKE detected after $(( $(date +%s)-DOWN ))s asleep"
    break
  fi
done
[ "$SPURIOUS" = "0" ] && say "  held asleep for $(( $(date +%s)-DOWN ))s with no spurious wake"

say "WAKE (magic packet)"
T2=$(date +%s); $PY "$(dirname "$0")/wol.py" $MAC >>"$LOG" 2>&1
PINGOK=0
for i in $(seq 1 180); do ping -c1 -W1 $H >/dev/null 2>&1 && { PINGOK=1; say "  PING back after $(( $(date +%s)-T2 ))s"; break; }; sleep 1; done
[ "$PINGOK" = "0" ] && { say "FAIL: no response 180s after magic packet — needs physical power-on"; exit 1; }
for i in $(seq 1 60); do ssh -n -o ConnectTimeout=3 $H true 2>/dev/null && { say "  SSH ready after $(( $(date +%s)-T2 ))s"; break; }; sleep 2; done

say "POST-SOAK HEALTH"
ssh -n $H 'nvidia-smi --query-gpu=index,memory.used,temperature.gpu,persistence_mode --format=csv,noheader | sed "s/^/  gpu /"
  echo "  suspend_stats/success: $(cat /sys/power/suspend_stats/success)  fail: $(cat /sys/power/suspend_stats/fail)"
  echo "  NVRM error lines this boot: $(journalctl -b --no-pager 2>/dev/null | grep -icE "NVRM.*(Xid|error)")"
  echo "  suspended seconds (BOOTTIME-MONOTONIC): $(python3 -c "import time;print(round(time.clock_gettime(time.CLOCK_BOOTTIME)-time.clock_gettime(time.CLOCK_MONOTONIC),1))")"
  echo "  wake source: $(journalctl -b --no-pager | grep -iE "PM: suspend exit|ACPI: Waking" | tail -2)"' | tee -a "$LOG"
say "SOAK COMPLETE (spurious wakes: $SPURIOUS)"
