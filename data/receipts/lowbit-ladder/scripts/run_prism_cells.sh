#!/usr/bin/env bash
# The prism-binary ladder cells: C-XBIN control first, then the two Bonsai containers.
#
# ORDER IS DELIBERATE. C-XBIN re-scores G-IQ2XS -- a model already measured on the buun binary --
# using the prism binary against the same ref.kld. It is two things at once:
#   1. Amendment 1's cross-binary control, which decides whether P-L2/P-L4 are valid at all.
#   2. The readiness probe for this binary. A successful BUILD is not evidence the binary can
#      read a .kld written by a different llama.cpp lineage. If the format is incompatible, it
#      surfaces here on a known-good model instead of mid-Bonsai and being misread as a Bonsai
#      defect.
# If C-XBIN yields no KLD block, the Bonsai cells are SKIPPED -- running them would produce
# numbers that cannot be interpreted.
#
# Same frozen invocation as every other cell. llama-perplexity exits 0 on failure; parse, do not
# trust rc.
set -u
BIN=/home/mark/prism_llama_cpp/build_sm60/bin/llama-perplexity
DIR=/mnt/HDD/ladder
OUT=/home/mark/ladder/cells
REF=/mnt/HDD/kld/ref.kld
CORPUS=/mnt/HDD/exl3/wiki.test.raw
mkdir -p "$OUT"
RESULTS="$OUT/results.jsonl"

run_one () {
  local id="$1" f="$2" m="$DIR/$2" log="$OUT/$1.log"
  echo "[$(date +%H:%M:%S)] CELL $id START $f" >> "$OUT/batch.log"
  if [ ! -f "$m" ]; then
    echo "[$(date +%H:%M:%S)] CELL $id MISSING $m" >> "$OUT/batch.log"
    printf '{"cell":"%s","file":"%s","status":"MISSING","binary":"prism"}\n' "$id" "$f" >> "$RESULTS"; sync
    return 1
  fi
  local sz t0 t1 rc
  sz=$(stat -c %s "$m"); t0=$(date +%s)
  "$BIN" -m "$m" -f "$CORPUS" \
    -ngl 99 -sm layer -c 512 -b 512 -ub 8 --chunks 40 -fa on -ctk f16 -ctv f16 \
    --kl-divergence-base "$REF" --kl-divergence > "$log" 2>&1
  rc=$?; t1=$(date +%s)
  local mean med p99 mx top ppl rms st
  mean=$(grep -oP 'Mean\s+KLD:\s*\K[-0-9.eE+]+'       "$log" | head -1)
  med=$(grep -oP  'Median\s+KLD:\s*\K[-0-9.eE+]+'     "$log" | head -1)
  p99=$(grep -oP  '99\.0%\s+KLD:\s*\K[-0-9.eE+]+'     "$log" | head -1)
  mx=$(grep -oP   'Maximum\s+KLD:\s*\K[-0-9.eE+]+'    "$log" | head -1)
  top=$(grep -oP  'Same\s+top\s+p:\s*\K[-0-9.eE+]+'   "$log" | head -1)
  ppl=$(grep -oP  'Mean PPL\(Q\)\s*:\s*\K[-0-9.eE+]+' "$log" | head -1)
  rms=$(grep -oP  'RMS\s+.p\s*:\s*\K[-0-9.eE+]+'      "$log" | head -1)
  if [ -z "${mean:-}" ] || [ -z "${top:-}" ]; then st=NO_RESULT; else st=OK; fi
  echo "[$(date +%H:%M:%S)] CELL $id $st rc=$rc mean=${mean:-none} same_top=${top:-none} ($((t1-t0))s)" >> "$OUT/batch.log"
  printf '{"cell":"%s","file":"%s","bytes":%s,"status":"%s","rc":%s,"secs":%s,"mean_kld":"%s","median_kld":"%s","p99_kld":"%s","max_kld":"%s","same_top":"%s","mean_ppl_q":"%s","rms_dp":"%s","binary":"prism","finished":"%s"}\n' \
    "$id" "$f" "$sz" "$st" "$rc" "$((t1-t0))" "${mean:-}" "${med:-}" "${p99:-}" "${mx:-}" "${top:-}" "${ppl:-}" "${rms:-}" "$(date -Is)" >> "$RESULTS"
  sync
  [ "$st" = OK ]
}

echo "PRISM_BATCH_START $(date -Is) binary=$BIN commit=$(cat /home/mark/ladder/prism_commit.txt 2>/dev/null)" >> "$OUT/batch.log"

if run_one C-XBIN Qwen3.8-27B-GSQ-RCO-IQ2_XS-mtp.gguf; then
  run_one B-PTQ1 Ternary-Bonsai-2-27B-PTQ1_0.gguf
  run_one B-PQ2  Ternary-Bonsai-2-27B-PQ2_0.gguf
else
  echo "[$(date +%H:%M:%S)] C-XBIN produced no result -- SKIPPING Bonsai cells (uninterpretable without the control)" >> "$OUT/batch.log"
fi
echo "PRISM_BATCH_DONE $(date -Is)" >> "$OUT/batch.log"
