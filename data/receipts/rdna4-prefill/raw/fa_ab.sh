#!/usr/bin/env bash
set -u
S=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
B=/mnt/TG_2TB/Projects/Apollo/engines/tq_head/build_rocm/bin/llama-bench
: > $S/fa_ab.log
for pair in "9B:/mnt/TG_2TB/AI/Models/Qwen3.5-9B-UD-Q2_K_XL.gguf" \
            "27B:/mnt/TG_2TB/AI/Models/gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"; do
  name="${pair%%:*}"; model="${pair#*:}"
  for mode in default tile mma; do
    echo "### $name / $mode" >> $S/fa_ab.log
    if [ "$mode" = default ]; then
      LD_LIBRARY_PATH="$(dirname $B)" env -u GGML_HIP_FA_KERNEL timeout 1800 "$B" \
        -m "$model" -ngl 99 -fa 1 -p 512 -n 128 -r 5 -o json > $S/fa_${name}_${mode}.json 2>/dev/null
    else
      LD_LIBRARY_PATH="$(dirname $B)" GGML_HIP_FA_KERNEL=$mode timeout 1800 "$B" \
        -m "$model" -ngl 99 -fa 1 -p 512 -n 128 -r 5 -o json > $S/fa_${name}_${mode}.json 2>/dev/null
    fi
    python3 -c "
import json
try:
    d=json.load(open('$S/fa_${name}_${mode}.json'))
    for r in d:
        lbl='pp512' if r.get('n_prompt') else 'tg128'
        s=r.get('samples_ts') or []
        print(f'  {lbl}: {r[\"avg_ts\"]:8.2f} +/- {r[\"stddev_ts\"]:5.2f}  samples={[round(x,2) for x in s]}')
except Exception as e: print('  (no data)', e)
" >> $S/fa_ab.log 2>&1
  done
done
echo "######## FA_AB DONE" >> $S/fa_ab.log
