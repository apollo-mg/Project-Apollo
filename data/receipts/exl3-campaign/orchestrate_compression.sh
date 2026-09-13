#!/bin/bash
# Orchestrates PREREG_EXL3_COMPRESSION.md (test 10) from the control plane. Launch detached FROM A
# FOREGROUND CALL. Runs six new KLD arms plus a cross-build bridge against the reference already on .73,
# appending to test 3's results.jsonl. Every check ABORTS; any abort after the proxy stops restores it.
set -u
cd /mnt/TG_2TB/Projects/Apollo || exit 1
D=data/receipts/exl3-campaign
OUTL=$D/kld
LOG=$OUTL/orchestrate_compression.log
PIDF=$OUTL/orchestrate_compression.pid
N=10.0.0.73
MAC=e0:d5:5e:b5:9e:b3
M=/mnt/TG_2TB/AI/Models
DM=apollo-proxy-deadman-comp-$(date +%H%M%S)
PROXY_STOPPED=0
DM_ARMED=0
# label | source on the control plane | destination on .73 | driver to use
ARMS=(
  "E25|$M/exl3/Qwen3.8-27B-exl3-2.50bpw|/mnt/HDD/exl3/Qwen3.8-27B-exl3-2.50bpw|old"
  "E30|$M/exl3/Qwen3.8-27B-exl3-3.00bpw|/mnt/HDD/exl3/Qwen3.8-27B-exl3-3.00bpw|old"
  "E35|$M/exl3/Qwen3.8-27B-exl3-3.50bpw|/mnt/HDD/exl3/Qwen3.8-27B-exl3-3.50bpw|old"
  "G2x|$M/Qwen3.8-27B-AD-IQ2_XS.gguf|/mnt/HDD/kld/Qwen3.8-27B-AD-IQ2_XS.gguf|old"
  "G3xx|$M/Qwen3.8-27B-AD-IQ3_XXS.gguf|/mnt/HDD/kld/Qwen3.8-27B-AD-IQ3_XXS.gguf|old"
  "G3m|$M/pelican3/Qwen3.8-27B.i1-IQ3_M.gguf|/mnt/HDD/kld/Qwen3.8-27B.i1-IQ3_M.gguf|old"
  "BRIDGE|$M/exl3/Qwen3.8-27B-exl3-3.00bpw|/mnt/HDD/exl3/Qwen3.8-27B-exl3-3.00bpw|new"
)
log () { echo "$(date '+%F %T') $*" >> "$LOG"; }
s73 () { timeout 120 ssh -o BatchMode=yes -o ConnectTimeout=8 "$N" "$@"; }
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
  echo "another compression orchestrator is running -- refusing"; exit 1
fi
echo $$ > "$PIDF"
log "orchestrator up (pid $$), ${#ARMS[@]} arms"

others_running () {
  local f p
  for f in $(find "$D" -name 'orchestrate*.pid' 2>/dev/null); do
    [ "$f" = "$PIDF" ] && continue
    p=$(cat "$f" 2>/dev/null)
    [ -n "$p" ] && kill -0 "$p" 2>/dev/null && return 0
  done
  return 1
}
free73 () {   # block only on TEST processes; the daily driver is stopped below, and a build counts too
  local out
  out=$(timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=8 "$N" 'ps -eo args | grep -c -E "[l]lama-perplexit|[l]lama-bench|[l]lama-server .*--port 8190|[c]make --build" || true' 2>/dev/null) || return 1
  [ "${out:-9}" = 0 ]
}
for i in $(seq 1 480); do
  if ! others_running && free73; then break; fi
  [ "$i" = 1 ] && log "waiting for .73 to be free (other orchestrator, test process, or a running build)"
  sleep 30
done
others_running && die "another campaign orchestrator is still running after 4 h"
free73 || die ".73 never went free after 4 h"
log ".73 is free"

systemd-run --user --unit="$DM" --on-active=300m /usr/bin/systemctl --user start apollo-wake-proxy >/dev/null 2>&1 \
  || die "could not arm the dead-man timer"
systemctl --user is-active --quiet "$DM.timer" || die "dead-man timer is not active"
DM_ARMED=1
log "dead-man $DM armed (restarts the proxy in 300 min)"
systemctl --user stop apollo-wake-proxy
PROXY_STOPPED=1
[ "$(systemctl --user is-active apollo-wake-proxy)" != active ] || die "proxy did not stop"
log "wake proxy STOPPED"

if ! ping -c1 -W1 "$N" >/dev/null 2>&1; then
  python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1); s.sendto(bytes.fromhex('ff' * 6 + '$MAC'.replace(':', '') * 16), ('10.0.0.255', 9))"
  log "sent magic packet to $MAC"
fi
for i in $(seq 1 18); do s73 true 2>/dev/null && break; sleep 5; done
s73 true || die ".73 not reachable over ssh"

scp -q -o BatchMode=yes "$D/exl3_kld_arm.py" "$N:exl3_kld_arm.py" || die "driver copy failed"
[ "$(sha256sum "$D/exl3_kld_arm.py" | awk '{print $1}')" = "$(s73 'sha256sum ~/exl3_kld_arm.py' | awk '{print $1}')" ] || die "staged driver differs"
NEWBIN=/mnt/HDD/buun-da458/build_sm60/bin/llama-perplexity
s73 "test -x $NEWBIN" || die "the da458765d build has no llama-perplexity yet"
log "drivers staged"

r=$(s73 'pkill -x llama-server; for i in $(seq 1 60); do u=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1); pgrep -x llama-server >/dev/null || [ "$u" -ge 500 ] || { echo CLEAR; exit 0; }; sleep 1; done; echo BUSY')
[ "$r" = CLEAR ] || die "GPUs on .73 did not clear (got: $r)"
log "GPUs clear"

for entry in "${ARMS[@]}"; do
  IFS='|' read -r LABEL SRC DST WHICH <<< "$entry"
  if s73 "grep '\"arm\": \"$LABEL\"' ~/exl3_kld/results.jsonl 2>/dev/null | grep -q '\"rc\": 0'"; then
    log "$LABEL already has a successful row -- skipping"
    continue
  fi
  [ -e "$SRC" ] || { log "$LABEL SKIPPED: $SRC missing on the control plane"; continue; }
  # A fetch directory exists from its first byte, so an in-flight download would look ready. If the
  # snapshot has a fetch log, it must say ALL FILES VERIFIED before the model is used.
  FLOG=$(dirname "$SRC")/fetch_$(basename "$SRC" | sed 's/.*-exl3-//').log
  if [ -f "$FLOG" ]; then
    for w in $(seq 1 60); do
      grep -q "ALL FILES VERIFIED" "$FLOG" && break
      [ "$w" = 1 ] && log "$LABEL: waiting for $(basename "$FLOG") to verify"
      sleep 30
    done
    grep -q "ALL FILES VERIFIED" "$FLOG" || { log "$LABEL SKIPPED: $(basename "$FLOG") never verified"; continue; }
  fi
  t0=$(date +%s)
  if [ -d "$SRC" ]; then
    s73 "mkdir -p $DST" || die "cannot create $DST"
    timeout 3600 rsync -a --partial "$SRC"/ "$N:$DST"/ || die "copy of $LABEL failed"
    (cd "$SRC" && sha256sum *.safetensors) > "$OUTL/manifest_$LABEL.txt" || die "manifest for $LABEL failed"
  else
    s73 "mkdir -p $(dirname "$DST")" || die "cannot create $(dirname "$DST")"
    timeout 3600 rsync -a --partial "$SRC" "$N:$DST" || die "copy of $LABEL failed"
    (cd "$(dirname "$SRC")" && sha256sum "$(basename "$SRC")") | awk -v n="$(basename "$DST")" '{print $1"  "n}' > "$OUTL/manifest_$LABEL.txt"
  fi
  scp -q -o BatchMode=yes "$OUTL/manifest_$LABEL.txt" "$N:manifest_$LABEL.txt" || die "manifest copy for $LABEL failed"
  log "$LABEL staged in $(( $(date +%s) - t0 )) s"

  ENVPREFIX=""
  [ "$WHICH" = new ] && ENVPREFIX="EXL3_KLD_BIN=$NEWBIN "
  s73 "cd ~ && ${ENVPREFIX}setsid nohup python3 -u exl3_kld_arm.py $LABEL '$DST' manifest_$LABEL.txt > ~/exl3_kld/run_$LABEL.out 2>&1 < /dev/null & echo \$! > ~/exl3_kld/run_$LABEL.pid"
  sleep 3
  RPID=$(s73 "cat ~/exl3_kld/run_$LABEL.pid")
  [ -n "$RPID" ] || die "$LABEL: driver pid not recorded"
  log "$LABEL running on .73, pid $RPID ($WHICH build)"
  t0=$(date +%s)
  while alive "$RPID"; do
    [ $(( $(date +%s) - t0 )) -gt 7200 ] && { log "$LABEL exceeded 120 min -- moving on"; break; }
    sleep 30
  done
  log "$LABEL finished in $(( $(date +%s) - t0 )) s"
done

restore
timeout 300 rsync -a --exclude '*.kld' "$N:exl3_kld/" "$OUTL/" && log "results pulled into the repo"
log "=== ORCHESTRATION COMPLETE ==="
rm -f "$PIDF"
