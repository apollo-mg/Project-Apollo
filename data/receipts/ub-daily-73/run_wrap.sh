#!/bin/bash
# Runs run_ub.sh, then on ANY exit: kill leftover cell servers by recorded PID on .73, drop the busy lock, and
# restore the wake proxy.
D=$(cd "$(dirname "$0")" && pwd)
"$D/run_ub.sh" "$@"
echo "runner exit $?"
ssh 10.0.0.73 'for f in ~/ub73/*.pid ~/ub73/*.smipid; do [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null; done; sleep 5; pgrep -x llama-server >/dev/null && echo LEFTOVER_SERVER || echo clean; P=$(cat /tmp/apollo-busy.ubtest 2>/dev/null); [ -n "$P" ] && kill "$P" 2>/dev/null; rm -f /tmp/apollo-busy.ubtest'
systemctl --user start apollo-wake-proxy && echo "PROXY_RESTORED $(date -Is)"
