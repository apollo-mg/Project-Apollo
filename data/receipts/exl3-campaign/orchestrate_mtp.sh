#!/bin/bash
# Orchestrates PREREG_EXL3_MTP_SWEEP.md from the control plane. Launch it detached FROM A FOREGROUND
# CALL. It WAITS for test 3's orchestrator to finish, then takes .73 itself. Every check ABORTS; any
# abort after the proxy stops restores it.
set -u
cd /mnt/TG_2TB/Projects/Apollo || exit 1
D=data/receipts/exl3-campaign
OUTL=$D/mtp
mkdir -p "$OUTL"
LOG=$OUTL/orchestrate.log
PIDF=$OUTL/orchestrate.pid
N=10.0.0.73
MAC=e0:d5:5e:b5:9e:b3
DM=apollo-proxy-deadman-mtp-$(date +%H%M%S)
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
  echo "another MTP orchestrator is running (pid $(cat "$PIDF")) -- refusing"; exit 1
fi
echo $$ > "$PIDF"
log "orchestrator up (pid $$)"

# 0. Wait until .73 is ACTUALLY FREE, and check it BEFORE touching the proxy.
#    2026-09-12: waiting on another orchestrator's pidfile treated its ABORT as success, so this script's
#    successor started while the KLD run still held both GPUs; it stopped and restarted the proxy on its
#    way out, and the next ledger run launched the daily driver into 21 GB of live test, which OOM'd.
#    The precondition is the node being free, not a pidfile being gone.
others_running () {
  local f
  for f in "$D"/kld/orchestrate.pid "$D"/mtp/orchestrate.pid "$D"/depth/orchestrate.pid; do
    [ "$f" = "$PIDF" ] && continue
    [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null && return 0
  done
  return 1
}
free73 () {   # comm is truncated to 15 chars, so match the prefix, never `pgrep -x llama-perplexity`
  local out n mem
  out=$(timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=8 "$N" 'ps -eo comm | grep -c "^llama-"; nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1' 2>/dev/null) || return 1
  n=$(printf '%s' "$out" | head -1); mem=$(printf '%s' "$out" | tail -1)
  [ "$n" = 0 ] && [ "${mem:-9999}" -lt 500 ] 2>/dev/null
}
for i in $(seq 1 480); do          # up to 4 h
  if ! others_running && free73; then break; fi
  [ "$i" = 1 ] && log "waiting for .73 to be free (another campaign orchestrator, or a live llama process)"
  sleep 30
done
others_running && die "another campaign orchestrator is still running after 4 h"
free73 || die ".73 never went free after 4 h (a llama process or GPU memory is still held)"
log ".73 is free"

# 1. Wait for the daily driver to be idle: two consecutive idle reads 30 s apart, at most 20 min.
reads=0
st=unset
for i in $(seq 1 40); do
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
[ "$reads" -ge 2 ] || die "daily driver never read idle twice in 20 min (last: $st)"
log "daily driver idle ($st)"

# 2. Arm the dead-man, then stop the proxy.
systemd-run --user --unit="$DM" --on-active=90m /usr/bin/systemctl --user start apollo-wake-proxy >/dev/null 2>&1 \
  || die "could not arm the dead-man timer"
systemctl --user is-active --quiet "$DM.timer" || die "dead-man timer is not active"
DM_ARMED=1
log "dead-man $DM armed (restarts the proxy in 90 min)"
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

# 4. Build llama-bench from the same tree as every other test, and check the commit it reports.
s73 'make -C ~/buun-sm60-qual/build_sm60qual llama-bench -j4 > ~/llama_bench_build.log 2>&1' || die "llama-bench build failed (see ~/llama_bench_build.log on .73)"
bv=$(s73 '~/buun-sm60-qual/build_sm60qual/bin/llama-bench --version 2>&1 | head -2')
case "$bv" in *9ae8f0f4*) log "llama-bench built: $bv" ;; *) die "llama-bench reports the wrong build: $bv" ;; esac

# 5. Stage the driver; refuse to mix runs; verify the copy.
s73 'test ! -e ~/exl3_mtp/results.jsonl' || die "an earlier sweep's results exist on .73 -- refusing to mix runs"
s73 'mkdir -p ~/exl3_mtp' || die "cannot create ~/exl3_mtp"
scp -q -o BatchMode=yes "$D/exl3_mtp_sweep.py" "$N:exl3_mtp_sweep.py" || die "copy of the driver failed"
[ "$(sha256sum "$D/exl3_mtp_sweep.py" | awk '{print $1}')" = "$(s73 'sha256sum ~/exl3_mtp_sweep.py' | awk '{print $1}')" ] || die "staged driver differs from the repo copy"
log "driver staged and verified"

# 6. Stop the daily driver's server and wait for empty GPUs.
r=$(s73 'pkill -x llama-server; for i in $(seq 1 60); do u=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1); pgrep -x llama-server >/dev/null || [ "$u" -ge 500 ] || { echo CLEAR; exit 0; }; sleep 1; done; echo BUSY')
[ "$r" = CLEAR ] || die "GPUs on .73 did not clear (got: $r)"
log "GPUs clear"

# 7. Launch the driver detached, and wait (an unreachable node counts as alive).
s73 'cd ~ && setsid nohup python3 -u exl3_mtp_sweep.py ALL > ~/exl3_mtp/run.out 2>&1 < /dev/null & echo $! > ~/exl3_mtp/run.pid'
sleep 3
RPID=$(s73 'cat ~/exl3_mtp/run.pid')
[ -n "$RPID" ] || die "driver pid was not recorded"
log "driver launched on .73, pid $RPID"
t0=$(date +%s)
while alive "$RPID"; do
  if [ $(( $(date +%s) - t0 )) -gt 3600 ]; then
    log "driver still running after 60 min -- leaving it; the dead-man restores the proxy at 90"
    rm -f "$PIDF"; exit 1
  fi
  sleep 30
done
log "driver finished"

# 8. Restore the proxy, disarm the dead-man, pull the results.
restore
timeout 180 rsync -a "$N:exl3_mtp/" "$OUTL/" && log "results pulled into the repo"
log "=== ORCHESTRATION COMPLETE ==="
rm -f "$PIDF"
