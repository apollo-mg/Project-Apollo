#!/bin/bash
# Orchestrates PREREG_EXL3_KLD.md from the control plane. Launch it detached FROM A FOREGROUND CALL:
# the harness's low-memory kill walks the process tree. Every check ABORTS; any abort after the proxy
# stops restores it. The three GGUFs are copied to .73 here; the driver re-hashes them there before use.
set -u
cd /mnt/TG_2TB/Projects/Apollo || exit 1
D=data/receipts/exl3-campaign
OUTL=$D/kld
mkdir -p "$OUTL"
LOG=$OUTL/orchestrate.log
PIDF=$OUTL/orchestrate.pid
N=10.0.0.73
MAC=e0:d5:5e:b5:9e:b3
M=/mnt/TG_2TB/AI/Models
FILES=("$M/qwen38-27b-ref/Qwen3.8-27B-Q8_0.gguf" "$M/unsloth-v3/Qwen3.8-27B-UD-IQ4_XS.gguf" "$M/unsloth-v3/Qwen3.8-27B-UD-Q4_K_M.gguf")
DM=apollo-proxy-deadman-kld-$(date +%H%M%S)
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

# 0. Never overlap test 1, and never run twice.
DPF=$D/dropin/orchestrate.pid
if [ -f "$DPF" ] && kill -0 "$(cat "$DPF")" 2>/dev/null; then
  echo "the test-1 orchestrator (pid $(cat "$DPF")) is still running -- refusing"; exit 1
fi
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "another KLD orchestrator is running (pid $(cat "$PIDF")) -- refusing"; exit 1
fi
echo $$ > "$PIDF"
log "orchestrator up (pid $$)"

# 1. Wait for the daily driver to be idle: two consecutive idle reads 30 s apart, at most 40 min.
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
systemd-run --user --unit="$DM" --on-active=180m /usr/bin/systemctl --user start apollo-wake-proxy >/dev/null 2>&1 \
  || die "could not arm the dead-man timer"
systemctl --user is-active --quiet "$DM.timer" || die "dead-man timer is not active"
DM_ARMED=1
log "dead-man $DM armed (restarts the proxy in 180 min)"
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

# 4. Stage the driver; refuse to mix runs; verify the copy byte-for-byte.
s73 'test ! -e ~/exl3_kld/results.jsonl && test ! -e /mnt/HDD/kld/ref.kld' || die "an earlier KLD run's results or reference exist on .73 -- refusing to mix runs"
s73 'mkdir -p ~/exl3_kld /mnt/HDD/kld' || die "cannot create directories on .73"
scp -q -o BatchMode=yes "$D/exl3_kld.py" "$N:exl3_kld.py" || die "copy of the driver failed"
[ "$(sha256sum "$D/exl3_kld.py" | awk '{print $1}')" = "$(s73 'sha256sum ~/exl3_kld.py' | awk '{print $1}')" ] || die "staged driver differs from the repo copy"
log "driver staged and verified"

# 5. Copy the three GGUFs (resumable). The driver re-hashes each against its published sha256 on .73.
for f in "${FILES[@]}"; do
  t0=$(date +%s)
  timeout 1800 rsync -a --partial "$f" "$N:/mnt/HDD/kld/" || die "copy of $(basename "$f") failed"
  log "copied $(basename "$f") in $(( $(date +%s) - t0 )) s"
done

# 6. Stop the daily driver's server (exact process name: cannot match this shell) and wait for empty GPUs.
r=$(s73 'pkill -x llama-server; for i in $(seq 1 60); do u=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1); pgrep -x llama-server >/dev/null || [ "$u" -ge 500 ] || { echo CLEAR; exit 0; }; sleep 1; done; echo BUSY')
[ "$r" = CLEAR ] || die "GPUs on .73 did not clear (got: $r)"
log "daily driver stopped, GPUs clear"

# 7. Launch the driver detached on .73, and wait (an unreachable node counts as alive).
s73 'cd ~ && setsid nohup python3 -u exl3_kld.py ALL > ~/exl3_kld/run.out 2>&1 < /dev/null & echo $! > ~/exl3_kld/run.pid'
sleep 3
RPID=$(s73 'cat ~/exl3_kld/run.pid')
[ -n "$RPID" ] || die "driver pid was not recorded"
log "driver launched on .73, pid $RPID"
t0=$(date +%s)
while alive "$RPID"; do
  if [ $(( $(date +%s) - t0 )) -gt 9000 ]; then
    log "driver still running after 150 min -- leaving it; the dead-man restores the proxy at 180"
    rm -f "$PIDF"; exit 1
  fi
  sleep 30
done
log "driver finished"

# 8. Restore the proxy, disarm the dead-man, pull everything except the 5 GB reference.
restore
timeout 180 rsync -a --exclude '*.kld' "$N:exl3_kld/" "$OUTL/" && log "results pulled into the repo"
log "=== ORCHESTRATION COMPLETE ==="
rm -f "$PIDF"
