#!/bin/bash
# Olmo 3 7B training ladder (Mark's OK, 11-25): base, Instruct-SFT, Instruct-DPO, Instruct (RL), RL-Zero-General.
# Every file of each repo to the NAS (except pytorch_model*.bin duplicates of the safetensors, 11-25); LFS files checked against the Hub's sha256. One repo at a time.
set -u
ROOT=/mnt/HDD/Models/olmo3-7b; L=$ROOT/download.log; mkdir -p $ROOT; echo "start $(date '+%F %T')" >> $L
for REPO in "$@"; do
  D=$ROOT/${REPO#allenai/}; mkdir -p $D; cd $D || exit 1
  curl -s -m 60 "https://huggingface.co/api/models/$REPO/tree/main" > files.json
  python3 -c "
import json
for f in json.load(open('files.json')):
    if f['type'] == 'file' and f['path'] != '.gitattributes' and not f['path'].startswith('pytorch_model'): print(f['path'], (f.get('lfs') or {}).get('oid', '-'))" > want.txt
  while read -r P OID; do
    if [ -f "$P" ] && [ "$OID" != "-" ] && [ "$(sha256sum "$P" | cut -c1-64)" = "$OID" ]; then echo "OK $REPO $P (already)" >> $L; continue; fi
    curl -sS -L --fail -o "$P" "https://huggingface.co/$REPO/resolve/main/$P" || { echo "FAIL download $REPO $P" >> $L; exit 1; }
    if [ "$OID" != "-" ]; then [ "$(sha256sum "$P" | cut -c1-64)" = "$OID" ] && echo "OK $REPO $P" >> $L || { echo "FAIL sha $REPO $P" >> $L; exit 1; }; fi
  done < want.txt
  echo "REPO_DONE $REPO $(date '+%F %T')" >> $L
done
echo "DOWNLOAD_DONE $(date '+%F %T')" >> $L
