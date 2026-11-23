#!/bin/bash
# Amendment 1: SenseNova-Loop-9B full-precision weights + code for the reference perplexity (Mark's OK, 11-23).
# Every file except mtp.safetensors, README_CN.md and assets/; LFS files checked against the Hub's sha256.
set -u
DST=/mnt/TG_2TB/AI/Models/sensenova-loop-9b-bf16; API=https://huggingface.co/api/models/sensenova/SenseNova-Loop-9B/tree/main
cd $DST || exit 1
curl -s $API > files.json
python3 -c "
import json
for f in json.load(open('files.json')):
    if f['type'] != 'file' or f['path'] in ('mtp.safetensors', 'README_CN.md', '.gitattributes'): continue
    print(f['path'], (f.get('lfs') or {}).get('oid', '-'))" > want.txt
while read -r P OID; do
  curl -sS -L --fail -C - -o "$P" "https://huggingface.co/sensenova/SenseNova-Loop-9B/resolve/main/$P" || { echo "FAIL download $P"; exit 1; }
  if [ "$OID" != "-" ]; then
    H=$(sha256sum "$P" | cut -c1-64); [ "$H" = "$OID" ] && echo "OK $P" || { echo "FAIL sha $P"; exit 1; }
  else echo "OK $P (no LFS hash)"; fi
done < want.txt
echo DOWNLOAD_DONE
