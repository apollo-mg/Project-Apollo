#!/bin/bash
# ThinkingCap forensic — finetune or repackage? One KLD pass vs OUR BF16 truth base.
# Real finetune => large divergence (different model, two-courts case study).
# Rebadged base => Q8-floor whisper (median ~1e-4, same-top 99%+).
# Waits for the fastfp16 A/B bench to free the GPUs.
set -u
PPL=/home/mark/llama_stock/build_carveout/bin/llama-perplexity
MODEL="/home/mark/AI/Models/Qwen 3.6/27B-ThinkingCap/ThinkingCap-Qwen3.6-27B-Q8_0-MTP.gguf"
BASE=/home/mark/quant_ladder/qwen27b_bf16_truth_f32kv_faoff_2k32.kld
OUT=/home/mark/quant_ladder

while [ ! -f "$OUT/ab_bench.DONE" ]; do sleep 300; done

echo "$(date '+%F %T') RUN thinkingcap-q8 vs BF16 truth base"
"$PPL" -m "$MODEL" -f /home/mark/wikitext-2-raw/wiki.test.raw \
  -c 2048 --chunks 32 -ctk f32 -ctv f32 -fa off -ngl 99 -ub 128 -ts 1,1,1,1 \
  --kl-divergence --kl-divergence-base "$BASE" \
  > "$OUT/kld_thinkingcap_q8.log" 2>&1
echo "$(date '+%F %T') exit=$?"
grep -E "Mean PPL|Median  KLD|Mean    KLD|Same top|99.0%   KLD" "$OUT/kld_thinkingcap_q8.log"
touch "$OUT/tc_forensic.DONE"
