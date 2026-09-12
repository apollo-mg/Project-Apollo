#!/bin/bash
# Runs PREREG_EXL3_KLD.md Amendment 2's extra arm (EXL3 5.00bpw) from the control plane. Launch it
# detached FROM A FOREGROUND CALL. It waits until .73 is genuinely free, copies the model, verifies it
# there against a manifest built here, and appends the arm to test 3's results against the same
# reference. Every check ABORTS; any abort after the proxy stops restores it.
set -u
cd /mnt/TG_2TB/Projects/Apollo || exit 1
D=data/receipts/exl3-campaign
OUTL=$D/kld
LOG=$OUTL/orchestrate_arm.log
PIDF=$OUTL/orchestrate_arm.pid
N=10.0.0.73
MAC=e0:d5:5e:b5:9e:b3
LABEL=E5
SRC=/mnt/TG_2TB/AI/Models/exl3/Qwen3.8-27B-exl3-5.00bpw
DST=/mnt/HDD/exl3/Qwen3.8-27B-exl3-5.00bpw
DM=apollo-proxy-deadman-kldarm-$(date +%H%M%S)
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
  echo "another arm orchestrator is running (pid $(cat "$PIDF")) -- refusing"; exit 1
fi
echo $$ > "$PIDF"
log "orchestrator up (pid $$) for arm $LABEL"

# 0. Wait for the download to finish and verify here first -- at most 40 min.
for i in $(seq 1 80); do
  grep -q "ALL FILES VERIFIED" /mnt/TG_2TB/AI/Models/exl3/fetch_5.00bpw.log 2>/dev/null && break
  grep -q "FILE(S) FAILED" /mnt/TG_2TB/AI/Models/exl3/fetch_5.00bpw.log 2>/dev/null && die "the 5.00bpw fetch failed verification"
  [ "$i" = 1 ] && log "waiting for the 5.00bpw fetch to verify"
  sleep 30
done
grep -q "ALL FILES VERIFIED" /mnt/TG_2TB/AI/Models/exl3/fetch_5.00bpw.log 2>/dev/null \
  || die "the 5.00bpw fetch did not verify within 40 min"
log "5.00bpw verified on the control plane"

# 1. Wait until .73 is genuinely free -- no other campaign orchestrator, no llama process, empty GPUs.
others_running () {   # enumerate EVERY orchestrator pidfile: a hardcoded list missed this script's own
  local f p                     # sibling on 2026-09-12 and two runs collided on .73
  for f in $(find "$D" -name 'orchestrate*.pid' 2>/dev/null); do
    [ "$f" = "$PIDF" ] && continue
    p=$(cat "$f" 2>/dev/null)
    [ -n "$p" ] && kill -0 "$p" 2>/dev/null && return 0
  done
  return 1
}
free73 () {   # Block only on TEST processes. The daily driver (port 8080) is stopped by this script in
  local out   # step 5, so gating on it deadlocks: a ledger request restarts it and the wait never ends.
  out=$(timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=8 "$N" 'ps -eo args | grep -c -E "[l]lama-perplexit|[l]lama-bench|[l]lama-server .*--port 8190" || true' 2>/dev/null) || return 1
  [ "${out:-9}" = 0 ]
}
for i in $(seq 1 480); do
  if ! others_running && free73; then break; fi
  [ "$i" = 1 ] && log "waiting for .73 to be free"
  sleep 30
done
others_running && die "another campaign orchestrator is still running after 4 h"
free73 || die ".73 never went free after 4 h"
log ".73 is free"

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

# 4. Refuse to score this arm twice, then copy the model and stage the driver + manifest.
# Refuse only if this arm already SUCCEEDED. A failed row (e.g. the 19:02 OOM when another run held the
# GPUs) stays in the file as data; the scorer takes the last row per arm.
s73 "grep '\"arm\": \"$LABEL\"' ~/exl3_kld/results.jsonl 2>/dev/null | grep -q '\"rc\": 0'" && die "arm $LABEL already has a successful row on .73"
s73 "mkdir -p $DST" || die "cannot create $DST"
t0=$(date +%s)
timeout 3600 rsync -a --partial "$SRC"/ "$N:$DST"/ || die "copy of the 5.00bpw model failed"
log "copied the model in $(( $(date +%s) - t0 )) s"
(cd "$SRC" && sha256sum *.safetensors) > "$OUTL/manifest_$LABEL.txt" || die "could not build the manifest"
scp -q -o BatchMode=yes "$OUTL/manifest_$LABEL.txt" "$N:manifest_$LABEL.txt" || die "manifest copy failed"
scp -q -o BatchMode=yes "$D/exl3_kld_arm.py" "$N:exl3_kld_arm.py" || die "driver copy failed"
[ "$(sha256sum "$D/exl3_kld_arm.py" | awk '{print $1}')" = "$(s73 'sha256sum ~/exl3_kld_arm.py' | awk '{print $1}')" ] || die "staged driver differs from the repo copy"
log "model, manifest and driver staged"

# 5. Stop any daily-driver server and wait for empty GPUs.
r=$(s73 'pkill -x llama-server; for i in $(seq 1 60); do u=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1); pgrep -x llama-server >/dev/null || [ "$u" -ge 500 ] || { echo CLEAR; exit 0; }; sleep 1; done; echo BUSY')
[ "$r" = CLEAR ] || die "GPUs on .73 did not clear (got: $r)"
log "GPUs clear"

# 6. Launch, and wait (an unreachable node counts as alive).
s73 "cd ~ && setsid nohup python3 -u exl3_kld_arm.py $LABEL $DST manifest_$LABEL.txt > ~/exl3_kld/run_$LABEL.out 2>&1 < /dev/null & echo \$! > ~/exl3_kld/run_$LABEL.pid"
sleep 3
RPID=$(s73 "cat ~/exl3_kld/run_$LABEL.pid")
[ -n "$RPID" ] || die "driver pid was not recorded"
log "driver launched on .73, pid $RPID"
t0=$(date +%s)
while alive "$RPID"; do
  if [ $(( $(date +%s) - t0 )) -gt 7200 ]; then
    log "driver still running after 120 min -- leaving it; the dead-man restores the proxy"
    rm -f "$PIDF"; exit 1
  fi
  sleep 30
done
log "driver finished"

# 7. Restore, and pull the extended results (never the 5 GB reference).
restore
timeout 180 rsync -a --exclude '*.kld' "$N:exl3_kld/" "$OUTL/" && log "results pulled into the repo"
log "=== ORCHESTRATION COMPLETE ==="
rm -f "$PIDF"
