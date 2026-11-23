#!/usr/bin/env bash
# The pi-adapter Hermes A/B main run (data/receipts/pi-hermes/PREREG_PI_HERMES.md): fixtures rebuilt on the run's UTC
# date, then all 83 families_v5 items for both arms side by side. Powers .194 off at the end (run_argus_pi.sh's trap).
set -u
A=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$A/runs/pi_main"
"$A/build_pi_fixtures.sh" >> "$A/runs/pi_main/fixtures.log" 2>&1 || { echo "fixture build failed" >> "$A/runs/pi_main/fixtures.log"; exit 1; }
ITEM_TIMEOUT=3600 "$A/run_argus_pi.sh" main
