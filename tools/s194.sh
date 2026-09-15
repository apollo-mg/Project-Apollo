#!/usr/bin/env bash
# Remote power control for .194 (Supermicro BMC at 10.0.0.195).
# Measured 2026-09-03: graceful shutdown 16s, cold boot to SSH 216s (3m36s),
# 218 W idle vs ~27 W standby. Boot is far too slow for a wake-on-demand proxy
# (cf. .73, which resumes from S3 in ~10s) -- this is deliberate manual control.
# Credentials are read from ~/.ipmi_194 (0600) and are NEVER stored in the repo.
set -uo pipefail
CFG=~/.ipmi_194
[ -r "$CFG" ] || { echo "missing $CFG (BMC_HOST/BMC_USER/BMC_PASS)"; exit 1; }
# Read values LITERALLY. Do not source: sourcing executes the file, so a password
# containing a quote, backtick, $ or \ either breaks parsing or runs as code.
BMC_HOST=$(sed -n 's/^BMC_HOST=//p' "$CFG" | head -1)
BMC_USER=$(sed -n 's/^BMC_USER=//p' "$CFG" | head -1)
BMC_PASS=$(sed -n 's/^BMC_PASS=//p' "$CFG" | head -1)
for v in BMC_HOST BMC_USER BMC_PASS; do
  eval "val=\${$v:-}"
  [ -n "$val" ] || { echo "$CFG: $v is empty or missing"; exit 1; }
done
HOST=10.0.0.194
B=(ipmitool -I lanplus -H "$BMC_HOST" -U "$BMC_USER" -P "$BMC_PASS")

# Surface IPMI failures instead of printing an empty field. A blank result was
# indistinguishable from "off", which is exactly the wrong thing for a power tool.
ipmi () {
  local out rc
  out=$("${B[@]}" "$@" 2>&1); rc=$?
  if [ $rc -ne 0 ]; then
    echo "IPMI ERROR: $(echo "$out" | head -1)" >&2
    return 1
  fi
  printf '%s\n' "$out"
}
pwr ()  { ipmi chassis power status | grep -oE 'on|off' | tail -1; }
watts (){ ipmi dcmi power reading | grep -i Instantaneous | grep -oE '[0-9]+ Watts'; }

case "${1:-status}" in
  status)
    echo "chassis : $(pwr)"
    echo "power   : $(watts)"
    if ssh -o ConnectTimeout=3 -o BatchMode=yes "$HOST" 'true' 2>/dev/null; then
      echo "ssh     : up  ($(ssh -o ConnectTimeout=3 "$HOST" uptime -p 2>/dev/null))"
    else
      echo "ssh     : down"
    fi ;;
  on)
    [ "$(pwr)" = on ] && { echo "already on"; exit 0; }
    "${B[@]}" chassis power on >/dev/null 2>&1
    echo "powering on -- measured ~216s to SSH, waiting..."
    T0=$(date +%s)
    for _ in $(seq 1 180); do
      ssh -o ConnectTimeout=3 -o BatchMode=yes "$HOST" 'true' 2>/dev/null && \
        { echo "up after $(( $(date +%s) - T0 ))s"; exit 0; }
      sleep 2
    done
    echo "did NOT come up within $(( $(date +%s) - T0 ))s"; exit 1 ;;
  off)
    # Refuse to pull the rug out from under a running job.
    BUSY=$(ssh -o ConnectTimeout=5 "$HOST" 'pgrep -x llama-server | wc -l' 2>/dev/null || echo 0)
    if [ "${BUSY:-0}" != "0" ] && [ "${2:-}" != "--force" ]; then
      echo "REFUSING: $BUSY llama-server process(es) running. Use '$0 off --force' to override."; exit 1
    fi
    echo "graceful shutdown (measured ~16s)..."
    ssh -o ConnectTimeout=5 "$HOST" 'sudo systemctl poweroff' >/dev/null 2>&1
    # Settle before reading watts: the PSU sensor lags the chassis state by ~20s, so reading it the
    # instant the chassis reports off returns the last ON figure. Measured 2026-09-15: 237 W
    # immediately after poweroff, 0 W twenty seconds later. Reporting the stale value made standby
    # look worse than running idle (218 W) and would have justified a hardware hunt for nothing.
    for _ in $(seq 1 45); do
      if [ "$(pwr)" = off ]; then
        echo "off. (settling 20s before reading standby draw -- the PSU sensor lags)"
        sleep 20
        echo "standby draw: $(watts)"
        exit 0
      fi
      sleep 2
    done
    echo "still on after 90s -- check manually"; exit 1 ;;
  *) echo "usage: $0 {on|off [--force]|status}"; exit 2 ;;
esac
