#!/bin/sh
O=/mnt/HDD/bench/nemotron-bolt-spin-1015; M="/mnt/models/AI_Models/Nemotron 3.5/Bolt-74B-A9B-24GB"
echo $$ > /tmp/apollo-busy.bolt-spin; trap "rm -f /tmp/apollo-busy.bolt-spin" EXIT
$O/leg.sh nodraft
$O/leg.sh lilicorr7 -md "$M/lilicorr/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB-LiLiCorr.gguf" -ngld 99 --spec-type draft-dflash --spec-draft-n-max 7
echo SPIN_DONE >> $O/state.log
