#!/bin/sh
# Draft-depth sweep (2026-10-15, after the n_max 7 spin): same-session no-draft control, n_max 2 and 3, n_max 7 with p_min 0.5.
O=/mnt/HDD/bench/nemotron-bolt-spin-1015; M="/mnt/models/AI_Models/Nemotron 3.5/Bolt-74B-A9B-24GB"
DR="$M/lilicorr/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB-LiLiCorr.gguf"
echo $$ > /tmp/apollo-busy.bolt-spin; trap "rm -f /tmp/apollo-busy.bolt-spin" EXIT
$O/leg.sh nodraft2
$O/leg.sh n2 -md "$DR" -ngld 99 --spec-type draft-dflash --spec-draft-n-max 2
$O/leg.sh n3 -md "$DR" -ngld 99 --spec-type draft-dflash --spec-draft-n-max 3
$O/leg.sh n7p05 -md "$DR" -ngld 99 --spec-type draft-dflash --spec-draft-n-max 7 --spec-draft-p-min 0.5
echo SWEEP_DONE >> $O/state.log
