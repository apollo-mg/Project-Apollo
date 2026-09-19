#!/usr/bin/env bash
# P-L0 gate -- Qwen3.8-27B-Q8_0 against its own reference ref.kld, on .73.
# Prereg: data/receipts/lowbit-ladder/PREREG_CODEC_LADDER.md
# Pass = mean KLD < 1e-4 AND same-top >= 99.9%.
#
# FROZEN INVOCATION from exl3_kld_arm.py -- do not vary a single flag.
# llama-perplexity EXITS 0 ON FAILURE: the verdict is parsed from output, never from rc.
set -u
BIN=/home/mark/buun-sm60-qual/build_sm60qual/bin/llama-perplexity
MODEL=/mnt/HDD/ladder/Qwen3.8-27B-Q8_0.gguf
OUT=/home/mark/ladder/gate_pl0
mkdir -p "$OUT"

{
  echo "host    $(hostname)"
  echo "date    $(date -Is)"
  echo "bin     $BIN"
  echo "model   $MODEL"
  echo "ref     /mnt/HDD/kld/ref.kld"
  echo "corpus  /mnt/HDD/exl3/wiki.test.raw"
  nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader
} > "$OUT/env.txt" 2>&1

"$BIN" -m "$MODEL" -f /mnt/HDD/exl3/wiki.test.raw \
  -ngl 99 -sm layer -c 512 -b 512 -ub 8 --chunks 40 -fa on -ctk f16 -ctv f16 \
  --kl-divergence-base /mnt/HDD/kld/ref.kld --kl-divergence \
  > "$OUT/run.log" 2>&1
echo "RC=$?" >> "$OUT/env.txt"
echo "GATE_RUN_FINISHED $(date -Is)" >> "$OUT/env.txt"
