#!/usr/bin/env bash
# S_code x2 then S_reason (PREREG_STRATA_9070 arms 1-2), sequential fresh starts.
cd "$(dirname "$0")"
CFG=/mnt/TG_2TB/Projects/strata/strata-coder-iq1_m.json; P=../gemma4-9070-spec
./run_strata.sh S_code_r1 $CFG $P/canonical_code-v1.txt
./run_strata.sh S_code_r2 $CFG $P/canonical_code-v1.txt
./run_strata.sh S_reason $CFG $P/canonical_reasoning-v1.txt
echo CHAIN1_DONE >> runs/run.log
