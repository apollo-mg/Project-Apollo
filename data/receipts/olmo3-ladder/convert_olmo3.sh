#!/bin/bash
# Olmo 3 ladder: each checkpoint to Q8_0 with mainline 33aeb17f8's converter (engines/rocm10/up_33aeb17f), output on the NAS.
set -u
R=/mnt/TG_2TB/Projects/Apollo; C=$R/engines/rocm10/up_33aeb17f/convert_hf_to_gguf.py; PY=$R/venv_cachyos/bin/python3
SRC=/mnt/HDD/Models/olmo3-7b; OUT=/mnt/HDD/Models/olmo3-7b-gguf; L=$R/data/receipts/olmo3-ladder/raw/convert.log
mkdir -p $OUT $R/data/receipts/olmo3-ladder/raw; cd /tmp
for M in "$@"; do
  $PY -E -s $C $SRC/$M --outtype q8_0 --outfile $OUT/$M-Q8_0.gguf > $R/data/receipts/olmo3-ladder/raw/convert_$M.log 2>&1
  rc=$?; echo "$M rc=$rc $( [ $rc = 0 ] && sha256sum < $OUT/$M-Q8_0.gguf | cut -c1-64 ) $(date '+%F %T')" >> $L
done
echo "CONVERT_DONE $(date '+%F %T')" >> $L
