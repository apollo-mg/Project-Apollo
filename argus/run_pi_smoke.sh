#!/usr/bin/env bash
# The pi-adapter Hermes A/B timing smoke (data/receipts/pi-hermes/): fixtures rebuilt on the run's UTC date, then four
# items per arm (two act: f1-referent-r1, f7-recipient-r3; two ask: f1-referent-r5, f4-unsat-r5). Sizing only.
set -u
A=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$A/runs/pi_smoke"
"$A/build_pi_fixtures.sh" >> "$A/runs/pi_smoke/fixtures.log" 2>&1 || { echo "fixture build failed" >> "$A/runs/pi_smoke/fixtures.log"; exit 1; }
ONLY="f1-referent-r1 f1-referent-r5 f4-unsat-r5 f7-recipient-r3" ITEM_TIMEOUT=3600 "$A/run_argus_pi.sh" smoke
