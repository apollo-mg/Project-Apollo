#!/bin/bash
# Chains the drift runs as their inputs become ready: CPU base after the desktop builds; each P100 node after its build,
# its model hashes and the CPU base; the desktop after the ROCm 10.1 measures and the CPU base.
# usage: orchestrate_drift.sh cpu|n194|n73|desk
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/stack-drift; S=$H/raw/state_orchestrate.log
log() { echo "$* $(date '+%F %T')" >> $S; }
H9=f904644baf031d09b45f86707faec876086377f57e077566f36eba48bcb5653c; H27=a680f44a06920e5d689774823782006aa3acc8db95750323373b24139b67e348
waitfor() { until eval "$1"; do sleep 60; done; }
case $1 in
  cpu)  waitfor 'grep -q BUILDS_DONE $H/raw/state_builds.log 2>/dev/null'; log "cpu: start"; bash $H/make_kld_base.sh ;;
  n194|n73)
    [ $1 = n194 ] && { HOST=mark@10.0.0.194; F9='~/AI/Models/sci-distill/Qwen3.5-9B-Q8_0.gguf'; F27='~/AI/Models/qwopus/Qwen3.8-27B-Q8_0.gguf'; }
    [ $1 = n73 ] && { HOST=mark@10.0.0.73; F9=/mnt/models/drift/Qwen3.5-9B-Q8_0.gguf; F27=/mnt/HDD/kld/Qwen3.8-27B-Q8_0.gguf; }
    waitfor "ssh -o BatchMode=yes $HOST 'grep -q BUILD_OK ~/build_33aeb17f.log' 2>/dev/null"
    log "$1: build ok; hashing"
    G9=$(ssh -o BatchMode=yes $HOST "sha256sum $F9 | cut -c1-64"); G27=$(ssh -o BatchMode=yes $HOST "sha256sum $F27 | cut -c1-64")
    [ "$G9" = $H9 ] && [ "$G27" = $H27 ] || { log "$1: STOP hash mismatch 9B=$G9 27B=$G27"; exit 1; }
    log "$1: hashes match"
    waitfor 'grep -q CPU_DONE $H/raw/state_drift_cpu.log 2>/dev/null && [ -s $H/raw/kld_base.bin ]'
    if [ $1 = n73 ]; then bash $H/run_drift_n73.sh; else bash $H/run_drift.sh n194; fi; log "$1: done" ;;
  desk)
    waitfor 'grep -q MEASURES_DONE $H/raw/state_measures.log 2>/dev/null && grep -q CPU_DONE $H/raw/state_drift_cpu.log 2>/dev/null'
    log "desk: start"; bash $H/run_drift.sh desk; log "desk: done" ;;
esac
