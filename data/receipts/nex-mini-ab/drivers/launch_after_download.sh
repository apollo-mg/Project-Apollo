#!/usr/bin/env bash
# Start the nex-mini-ab three-way once all downloads have finished. three_way.sh itself
# refuses to run unless every file has a VERIFIED line in download.log.
L=/home/mark/AI/Models/nex-mini-ab/download.log
until grep -q "=== downloads done ===" "$L"; do sleep 30; done
exec /home/mark/hep/three_way.sh
