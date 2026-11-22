#!/usr/bin/env bash
# Fixtures for the pi-adapter Hermes A/B (data/receipts/pi-hermes/). Two arms run side by side, each with its own world,
# HERMES_HOME and gateway port (make_fixture.sh), on both v5 worlds:
#   hbA, hbB  -> BASE arm, model on 127.0.0.1:8091 (tunnel to .194 lane A)
#   hpA, hpB  -> PIA arm,  model on 127.0.0.1:8092 (tunnel to .194 lane B)
# make_fixture.sh anchors the fake calendar to TODAY IN UTC, so build on the run's UTC date. Existing fixtures of these
# names are moved to the trash first (never deleted). Names are alphanumeric: run_9b_gate.sh's SKILL.md check expects it.
set -euo pipefail
A=$(cd "$(dirname "$0")" && pwd)
for spec in hbA:8671:A:8091 hbB:8672:B:8091 hpA:8673:A:8092 hpB:8674:B:8092; do
    IFS=: read -r FX GW WORLD MPORT <<< "$spec"
    for old in "$A/fixtures/$FX" "$A/fixtures/$FX.agent-home.pristine.tar"; do
        [ -e "$old" ] && gio trash "$old"
    done
    if [ "$WORLD" = B ]; then WORLD=B "$A/make_fixture.sh" "$FX" "$GW" >/dev/null; else "$A/make_fixture.sh" "$FX" "$GW" >/dev/null; fi
    CFG="$A/fixtures/$FX/agent-home/config.yaml"
    sed -i "s|base_url: http://127.0.0.1:[0-9]*/v1|base_url: http://127.0.0.1:$MPORT/v1|; s|default: Qwen3.8-27B-UD-IQ3_XXS|default: Qwen3.8-27B-Q8_0|" "$CFG"
    grep -q "base_url: http://127.0.0.1:$MPORT/v1" "$CFG" || { echo "FAIL: $FX not pointed at :$MPORT"; exit 1; }
    tar -cf "$A/fixtures/$FX.agent-home.pristine.tar" -C "$A/fixtures/$FX" agent-home
    echo "fixture $FX: world $WORLD, gateway $GW, model :$MPORT, calendar $(TZ=UTC date +%F), pristine $(sha256sum < "$A/fixtures/$FX.agent-home.pristine.tar" | cut -c1-12)"
done
