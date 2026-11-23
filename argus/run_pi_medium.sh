#!/usr/bin/env bash
# PREREG_PI_HERMES.md Amendment 1: the same 83 items with thinking on at medium, both arms side by side.
set -u
A=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$A/runs/pi_medium"
"$A/build_pi_fixtures.sh" >> "$A/runs/pi_medium/fixtures.log" 2>&1 || { echo "fixture build failed" >> "$A/runs/pi_medium/fixtures.log"; exit 1; }
THINK=medium ITEM_TIMEOUT=3600 "$A/run_argus_pi.sh" medium
