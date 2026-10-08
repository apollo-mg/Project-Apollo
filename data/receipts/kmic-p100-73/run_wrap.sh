#!/bin/bash
# Runs run_kmic.sh, then on ANY exit: kill leftover cell servers by recorded PID on .73 and restore the wake proxy.
D=$(cd "$(dirname "$0")" && pwd)
"$D/run_kmic.sh" "$@"
echo "runner exit $?"
ssh 10.0.0.73 'for f in ~/kmic73/*.pid ~/kmic73/*.smipid; do [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null; done; sleep 5; pgrep -x llama-server >/dev/null && echo LEFTOVER_SERVER || echo clean'
systemctl --user start apollo-wake-proxy && echo "PROXY_RESTORED $(date -Is)"
