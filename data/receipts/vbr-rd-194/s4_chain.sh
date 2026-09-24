#!/bin/bash
# Runs ON .194. REF on GPU 0, then four GPU queues in parallel. Each queue is sequential; arms are resumable.
# Queues interleave static and VBR arms so that no GPU carries only one kind.
set -u
cd ~/s4
./run_s4.sh REF 0 || { echo "######## CHAIN ABORT (REF)"; exit 1; }
q () { local g=$1; shift; for a in "$@"; do ./run_s4.sh $a $g; done; }
q 0 VF  Q8  V16 > logs/q0.log 2>&1 &
q 1 V75 Q4  V22 > logs/q1.log 2>&1 &
q 2 V55 T4  V29 > logs/q2.log 2>&1 &
q 3 V40 T3      > logs/q3.log 2>&1 &
wait
cat logs/q?.log
echo "######## S4 DONE $(date -Is)"
