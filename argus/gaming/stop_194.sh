#!/usr/bin/env bash
# Safety net for runs on .194 (ExecStopPost): stop any llama-server by its listening port, verified by the binary's
# name, then power .194 off. tools/s194.sh refuses to power off while a llama-server runs, which is what left .194 on
# with two models loaded when calibration v1 was stopped on 2026-11-17.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; H=10.0.0.194
ssh -o BatchMode=yes -o ConnectTimeout=10 "$H" 'for p in 8190 8191 8192 8193; do pid=$(ss -ltnp 2>/dev/null | grep ":$p " | sed -n "s/.*pid=\([0-9]*\).*/\1/p" | head -1); [ -n "$pid" ] && [ "$(readlink /proc/$pid/exe | xargs basename)" = llama-server ] && kill "$pid"; done; for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' || echo "stop_194: a llama-server is still running or .194 is unreachable"
"$ROOT/tools/s194.sh" off
