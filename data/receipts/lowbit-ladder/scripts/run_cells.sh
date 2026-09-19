#!/usr/bin/env bash
# The five stock-GGUF ladder cells, run serially on .73 against ref.kld.
#
# FROZEN INVOCATION -- byte-identical to the P-L0 gate and to exl3_kld_arm.py. Not one flag
# varies between cells, and the device configuration (both P100s, -sm layer) is the same one
# that produced ref.kld and passed the gate. Running one cell per GPU would halve wall clock
# and is deliberately NOT done: it changes the execution configuration the reference was made
# under, to save time on a measurement whose whole value is comparability.
#
# llama-perplexity EXITS 0 ON FAILURE. Every verdict is parsed; rc is recorded and ignored.
# A cell that yields no KLD block is logged NO_RESULT and the batch CONTINUES -- one bad cell
# must not cost the other four.
set -u
BIN=/home/mark/buun-sm60-qual/build_sm60qual/bin/llama-perplexity
DIR=/mnt/HDD/ladder
OUT=/home/mark/ladder/cells
REF=/mnt/HDD/kld/ref.kld
CORPUS=/mnt/HDD/exl3/wiki.test.raw
mkdir -p "$OUT"
RESULTS="$OUT/results.jsonl"

cells=(
  "G-IQ2XS:Qwen3.8-27B-GSQ-RCO-IQ2_XS-mtp.gguf"
  "A-IQ2XS:Qwen3.8-27B-AD-IQ2_XS.gguf"
  "G-IQ3XXS:Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
  "A-IQ3XXS:Qwen3.8-27B-AD-IQ3_XXS.gguf"
  "A-IQ3S:Qwen3.8-27B-AD-IQ3_S-IQ3_XXS.gguf"
)

echo "BATCH_START $(date -Is)" >> "$OUT/batch.log"
for entry in "${cells[@]}"; do
  id="${entry%%:*}"; f="${entry#*:}"; m="$DIR/$f"
  log="$OUT/$id.log"
  echo "[$(date +%H:%M:%S)] CELL $id START $f" >> "$OUT/batch.log"

  if [ ! -f "$m" ]; then
    echo "[$(date +%H:%M:%S)] CELL $id MISSING $m" >> "$OUT/batch.log"
    printf '{"cell":"%s","file":"%s","status":"MISSING"}\n' "$id" "$f" >> "$RESULTS"
    sync; continue
  fi

  sz=$(stat -c %s "$m")
  t0=$(date +%s)
  "$BIN" -m "$m" -f "$CORPUS" \
    -ngl 99 -sm layer -c 512 -b 512 -ub 8 --chunks 40 -fa on -ctk f16 -ctv f16 \
    --kl-divergence-base "$REF" --kl-divergence > "$log" 2>&1
  rc=$?
  t1=$(date +%s)

  # Parse. The KLD block is the only evidence a cell produced anything.
  mean=$(grep -oP 'Mean\s+KLD:\s*\K[-0-9.eE+]+'   "$log" | head -1)
  med=$(grep -oP  'Median\s+KLD:\s*\K[-0-9.eE+]+' "$log" | head -1)
  p99=$(grep -oP  '99\.0%\s+KLD:\s*\K[-0-9.eE+]+' "$log" | head -1)
  mx=$(grep -oP   'Maximum\s+KLD:\s*\K[-0-9.eE+]+' "$log" | head -1)
  top=$(grep -oP  'Same\s+top\s+p:\s*\K[-0-9.eE+]+' "$log" | head -1)
  ppl=$(grep -oP  'Mean PPL\(Q\)\s*:\s*\K[-0-9.eE+]+' "$log" | head -1)
  rms=$(grep -oP  'RMS\s+.p\s*:\s*\K[-0-9.eE+]+' "$log" | head -1)

  if [ -z "${mean:-}" ] || [ -z "${top:-}" ]; then
    st=NO_RESULT
    echo "[$(date +%H:%M:%S)] CELL $id NO_RESULT rc=$rc (no KLD block; rc is meaningless here)" >> "$OUT/batch.log"
  else
    st=OK
    echo "[$(date +%H:%M:%S)] CELL $id OK mean=$mean same_top=$top ($((t1-t0))s)" >> "$OUT/batch.log"
  fi

  # Incremental persistence: one line per cell, flushed and fsynced before the next cell starts.
  printf '{"cell":"%s","file":"%s","bytes":%s,"status":"%s","rc":%s,"secs":%s,"mean_kld":"%s","median_kld":"%s","p99_kld":"%s","max_kld":"%s","same_top":"%s","mean_ppl_q":"%s","rms_dp":"%s","finished":"%s"}\n' \
    "$id" "$f" "$sz" "$st" "$rc" "$((t1-t0))" "${mean:-}" "${med:-}" "${p99:-}" "${mx:-}" "${top:-}" "${ppl:-}" "${rms:-}" "$(date -Is)" >> "$RESULTS"
  sync
done
echo "BATCH_DONE $(date -Is)" >> "$OUT/batch.log"
