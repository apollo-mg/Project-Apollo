#!/bin/bash
MODEL="/home/mark/AI/Models/Qwen 3.6/27B/Qwen3.6-27B-Q6_K.gguf"
CORPUS="/home/mark/wikitext-2-raw/wiki.test.raw"
BASE="/home/mark/qwen-base-logits-kld/base_q6_f32kv_faoff_ctx2048_32ch_PATCHED.kld"
OUT="/home/mark/kld_certificate_p100_sli.txt"

echo "Running KLD Certificate test on $(hostname)..."
echo "Date: $(date)" > "$OUT"
echo "Model: $MODEL" >> "$OUT"
echo "Base: $BASE" >> "$OUT"
echo "Config: f16 KV, FA off, layer split, SM60 carve-out patched, batch 2048" >> "$OUT"
echo "--------------------------------------------------" >> "$OUT"

/home/mark/buun_vbr/build/bin/llama-perplexity \
  -m "$MODEL" -f "$CORPUS" -c 2048 -b 2048 -ub 2048 -t 16 -ngl 99 \
  -ctk f16 -ctv f16 -fa off \
  --kl-divergence --kl-divergence-base "$BASE" >> "$OUT" 2>&1

echo "Done. Certificate saved to $OUT"
