#!/usr/bin/env bash
set -u
D=/home/mark/models
url="https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-UD-IQ2_M.gguf"
echo "### $(date -Is) fetching UD-IQ2_M"
curl -L -C - --retry 5 --retry-delay 10 --fail -o "$D/Qwen3.8-27B-UD-IQ2_M.gguf" "$url" \
  || { echo "### FAILED iq2"; exit 1; }
echo "### $(date -Is) done $(stat -c%s "$D/Qwen3.8-27B-UD-IQ2_M.gguf") bytes"
sha256sum "$D/Qwen3.8-27B-UD-IQ2_M.gguf"
df -h / | tail -1
echo "### IQ2 DOWNLOAD DONE"
