#!/usr/bin/env bash
# Restore everything the gate touched: gateway down, arm server down, agent-home config
# restored from backup, wake proxy back up (which restores Mark's daily driver itself).
set -u
A=/mnt/TG_2TB/Projects/Apollo/argus
G=$(cat /tmp/argus_gateway.pid 2>/dev/null || true)
if [ -n "${G:-}" ] && [ -d /proc/$G ]; then kill -TERM "$G" && echo "gateway $G stopped"; else echo "gateway already gone"; fi
ssh -n -o BatchMode=yes mark@10.0.0.73 'for f in ~/argus_*.pid; do [ -f "$f" ] || continue
  P=$(cat "$f"); [ -d /proc/$P ] && { kill -TERM "$P"; echo "  arm server $P stopped"; }; rm -f "$f"; done
  sleep 3; nvidia-smi --query-gpu=index,memory.used --format=csv,noheader'
[ -f "$A/agent-home/config.yaml.orig" ] && { cp "$A/agent-home/config.yaml.orig" "$A/agent-home/config.yaml"; echo "agent-home config restored"; }
systemctl --user start apollo-wake-proxy && echo "wake proxy restarted"
sleep 5
curl -s -m 120 -X POST 127.0.0.1:8099/wake; echo
curl -s -m 10 127.0.0.1:8099/status; echo
