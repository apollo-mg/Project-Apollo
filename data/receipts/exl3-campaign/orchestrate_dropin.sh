#!/bin/bash
# Orchestrates PREREG_EXL3_DROPIN.md from the control plane. Launch it detached FROM A FOREGROUND CALL:
# the harness's low-memory kill walks the process tree. Every check ABORTS -- a printed warning is not
# a check (lesson of the 2026-09-12 v2 misfire). Any abort after the proxy stops restores it.
set -u
cd /mnt/TG_2TB/Projects/Apollo || exit 1
D=data/receipts/exl3-campaign
OUTL=$D/dropin
mkdir -p "$OUTL"
LOG=$OUTL/orchestrate.log
PIDF=$OUTL/orchestrate.pid
N=10.0.0.73
MAC=e0:d5:5e:b5:9e:b3
DM=apollo-proxy-deadman-dropin-$(date +%H%M%S)
PROXY_STOPPED=0
DM_ARMED=0
log () { echo "$(date '+%F %T') $*" >> "$LOG"; }
s73 () { timeout 60 ssh -o BatchMode=yes -o ConnectTimeout=8 "$N" "$@"; }
restore () {
  if [ "$PROXY_STOPPED" = 1 ]; then
    systemctl --user start apollo-wake-proxy
    log "wake proxy RESTARTED -> $(systemctl --user is-active apollo-wake-proxy)"
  fi
  if [ "$DM_ARMED" = 1 ]; then
    systemctl --user stop "$DM.timer" 2>/dev/null
    log "dead-man $DM disarmed"
  fi
}
die () { log "ABORT: $*"; restore; rm -f "$PIDF"; exit 1; }
alive () { local st; st=$(timeout 20 ssh -o BatchMode=yes "$N" "kill -0 $1 2>/dev/null && echo ALIVE || echo DEAD" 2>/dev/null); [ "$st" != "DEAD" ]; }

if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "another orchestrator is running (pid $(cat "$PIDF")) -- refusing"; exit 1
fi
echo $$ > "$PIDF"
log "orchestrator up (pid $$)"

# 1. Wait for the daily driver to be idle: two consecutive idle reads 30 s apart, at most 40 min.
#    A failed ssh is not evidence of idle; an asleep node is.
reads=0
st=unset
for i in $(seq 1 80); do
  if ! ping -c1 -W1 "$N" >/dev/null 2>&1; then
    st=asleep
  elif out=$(s73 'curl -s -m 5 127.0.0.1:8080/slots || echo NOSERVER'); then
    if [ "$out" = NOSERVER ]; then st=noserver; else
      st=$(printf '%s' "$out" | python3 -c 'import json, sys
try:
    print("busy" if any(s.get("is_processing") for s in json.load(sys.stdin)) else "idle")
except Exception:
    print("unparsed")')
    fi
  else
    st=ssh-failed
  fi
  case "$st" in asleep|noserver|idle) reads=$((reads + 1)) ;; *) reads=0 ;; esac
  [ "$reads" -ge 2 ] && break
  sleep 30
done
[ "$reads" -ge 2 ] || die "daily driver never read idle twice in 40 min (last: $st) -- not interrupting it"
log "daily driver idle ($st)"

# 2. Arm the dead-man, then stop the proxy.
systemd-run --user --unit="$DM" --on-active=120m /usr/bin/systemctl --user start apollo-wake-proxy >/dev/null 2>&1 \
  || die "could not arm the dead-man timer"
systemctl --user is-active --quiet "$DM.timer" || die "dead-man timer is not active"
DM_ARMED=1
log "dead-man $DM armed (restarts the proxy in 120 min)"
systemctl --user stop apollo-wake-proxy
PROXY_STOPPED=1
[ "$(systemctl --user is-active apollo-wake-proxy)" != active ] || die "proxy did not stop"
log "wake proxy STOPPED"

# 3. Wake .73 if the proxy had suspended it.
if ! ping -c1 -W1 "$N" >/dev/null 2>&1; then
  python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1); s.sendto(bytes.fromhex('ff' * 6 + '$MAC'.replace(':', '') * 16), ('10.0.0.255', 9))"
  log "sent magic packet to $MAC"
fi
for i in $(seq 1 18); do s73 true 2>/dev/null && break; sleep 5; done
s73 true || die ".73 not reachable over ssh"

# 4. Stage the driver and probe; refuse to append to an earlier run; verify the copies byte-for-byte.
s73 'test ! -e ~/exl3_dropin/results.jsonl' || die "results.jsonl already exists on .73 -- refusing to mix runs"
s73 'mkdir -p ~/exl3_dropin' || die "cannot create ~/exl3_dropin on .73"
scp -q -o BatchMode=yes "$D/exl3_dropin.py" "$N:exl3_dropin.py" || die "copy of the driver failed"
scp -q -o BatchMode=yes "$D/vision_probe.png" "$N:exl3_dropin/vision_probe.png" || die "copy of the probe failed"
want=$(sha256sum "$D/exl3_dropin.py" "$D/vision_probe.png" | awk '{print $1}' | tr '\n' ' ')
got=$(s73 'sha256sum ~/exl3_dropin.py ~/exl3_dropin/vision_probe.png' | awk '{print $1}' | tr '\n' ' ')
[ -n "$want" ] && [ "$want" = "$got" ] || die "staged files differ from the repo copies"
log "driver + probe staged and verified"

# 5. Stop the daily driver's server (exact process name: cannot match this shell) and wait for empty GPUs.
r=$(s73 'pkill -x llama-server; for i in $(seq 1 60); do u=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1); pgrep -x llama-server >/dev/null || [ "$u" -ge 500 ] || { echo CLEAR; exit 0; }; sleep 1; done; echo BUSY')
[ "$r" = CLEAR ] || die "GPUs on .73 did not clear (got: $r)"
log "daily driver stopped, GPUs clear"

# 6. Launch the driver detached on .73.
s73 'cd ~ && setsid nohup python3 -u exl3_dropin.py ALL > ~/exl3_dropin/run.out 2>&1 < /dev/null & echo $! > ~/exl3_dropin/run.pid'
sleep 3
RPID=$(s73 'cat ~/exl3_dropin/run.pid')
[ -n "$RPID" ] || die "driver pid was not recorded"
log "driver launched on .73, pid $RPID"

# 7. Wait for it (an unreachable node counts as alive: never restore the proxy under a running test).
t0=$(date +%s)
while alive "$RPID"; do
  if [ $(( $(date +%s) - t0 )) -gt 6000 ]; then
    log "driver still running after 100 min -- leaving it; the dead-man restores the proxy at 120"
    rm -f "$PIDF"; exit 1
  fi
  sleep 30
done
log "driver finished"

# 8. Restore the proxy, disarm the dead-man, pull everything into the repo.
restore
timeout 180 rsync -a "$N:exl3_dropin/" "$OUTL/" && log "results pulled into the repo"
log "=== ORCHESTRATION COMPLETE ==="
rm -f "$PIDF"
