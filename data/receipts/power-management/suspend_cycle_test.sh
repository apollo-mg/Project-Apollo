#!/usr/bin/env bash
# Dry run: S3 suspend -> Wake-on-LAN -> verify GPUs survived.
# Preconditions checked first: no llama-server (so NO VRAM spill is attempted -- /var has 24 GiB
# free against 32 GiB of VRAM, which is the trap), and GPUs idle.
# If resume fails, .73 needs a physical power button press. Nothing else is at risk: the box
# holds no running job.
set -u
H=10.0.0.73; MAC=e0:d5:5e:b5:9e:b3
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
t () { date +%s.%N; }
echo "=== PRE-FLIGHT $(date -Iseconds)"
ssh -n -o ConnectTimeout=10 $H 'echo "  llama-server procs: $(pgrep -xc llama-server)"
  nvidia-smi --query-gpu=index,name,memory.used,temperature.gpu,persistence_mode --format=csv,noheader | sed "s/^/  /"
  echo "  uptime: $(uptime -p)"; echo "  kernel: $(uname -r)"' || { echo "ABORT: .73 unreachable"; exit 1; }
N=$(ssh -n $H 'pgrep -xc llama-server')
[ "$N" != "0" ] && { echo "ABORT: llama-server running -- suspend would try a 32 GiB VRAM spill into 24 GiB"; exit 1; }

echo; echo "=== SUSPEND"
T0=$(t)
ssh -n $H 'sudo -n systemd-run --on-active=2 --timer-property=AccuracySec=100ms systemctl suspend' \
  || { echo "ABORT: could not schedule suspend (sudo/polkit)"; exit 1; }
echo "  suspend scheduled; waiting for the host to go down..."
for i in $(seq 1 60); do ping -c1 -W1 $H >/dev/null 2>&1 || { T1=$(t); echo "  DOWN after $(awk "BEGIN{printf \"%.1f\", $T1-$T0}")s"; break; }; sleep 1; done
ping -c1 -W1 $H >/dev/null 2>&1 && { echo "  FAIL: still responding after 60s -- suspend did not take"; exit 1; }
sleep 10   # let it settle fully into S3 before poking it

echo; echo "=== WAKE (magic packet)"
T2=$(t); $PY wol.py $MAC
for i in $(seq 1 120); do ping -c1 -W1 $H >/dev/null 2>&1 && { T3=$(t); echo "  PING back after $(awk "BEGIN{printf \"%.1f\", $T3-$T2}")s"; break; }; sleep 1; done
ping -c1 -W1 $H >/dev/null 2>&1 || { echo "  FAIL: no response 120s after magic packet -- needs physical power-on"; exit 1; }
for i in $(seq 1 60); do ssh -n -o ConnectTimeout=3 $H true 2>/dev/null && { T4=$(t); echo "  SSH ready after $(awk "BEGIN{printf \"%.1f\", $T4-$T2}")s"; break; }; sleep 2; done

echo; echo "=== POST-RESUME GPU HEALTH"
ssh -n $H 'nvidia-smi --query-gpu=index,name,memory.used,temperature.gpu,persistence_mode --format=csv,noheader | sed "s/^/  /"
  echo "  uptime: $(uptime -p)"
  echo "  suspend/resume in journal:"; journalctl -b -n 200 --no-pager 2>/dev/null | grep -icE "PM: suspend entry|PM: suspend exit" | sed "s/^/    matches: /"
  echo "  nvidia errors since resume:"; journalctl -b --no-pager 2>/dev/null | grep -icE "NVRM.*(Xid|error)" | sed "s/^/    NVRM error lines: /"'
echo; echo "=== CYCLE COMPLETE $(date -Iseconds)"
