#!/usr/bin/env bash
# U5d - replacement low-bit tier after U5c 4-bit mixed arms hit a kernel coverage gap.
#
# q4_0+turbo4 aborts at fattn.cu:2658 (BEST_FATTN_KERNEL_NONE) both ways on sm_60.
# The enumeration just above that line lists what buun actually supports mixed:
#   K=TURBO2_0 with V in {TURBO3_0, TURBO4_0, Q8_0, F16};  K=TURBO3_0 with V=TURBO2_0
# q4_0 is not in the turbo mixing story at all - the non-turbo partner is q8_0/f16.
#
# So the tier is rebuilt on turbo2/turbo3, which is BETTER than the q4_0 design:
# the two mixed arms are an EXACT SWAP of the same two codecs, so placement is
# tested with no codec-quality confound (the 8-bit tier had one: turbo8 vs q8_0
# differ in codec AND width).
#   A turbo3/turbo3 7.0 | B turbo3/turbo2 6.0 | C turbo2/turbo3 6.0 | D turbo2/turbo2 5.0
#   (turbo3 3.5 bpv = 14B/32, turbo2 2.5 bpv = 10B/32)
set -u
B=~/buun_tree_current/build/bin/llama-frontier-hazard
M=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
P=~/hazard_prompts_128.txt
OUT=~/u5d_raw
mkdir -p "$OUT"
# wait for U5c to release the GPUs
while ! grep -q "U5c DONE" ~/u5c.log 2>/dev/null; do sleep 20; done
sleep 10
echo "### U5d SWAP TIER - .194 sm_60, buun 02f8581, $(basename $M)  $(date -Is)"
echo "### 128 prompts, n_prefix 128, n_score 128. B and C are an exact codec swap at 6.0 bpv."
nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader | sed "s/^/###   /"
echo
printf "%-16s %-8s %-10s %-10s %-10s %-10s %-10s\n" "K/V" "tot_bpv" "flip_rate" "mean_KL" "mean_R" "cvar95_R" "frac_L>=1"
for spec in "turbo3:turbo3:7.0" "turbo3:turbo2:6.0" "turbo2:turbo3:6.0" "turbo2:turbo2:5.0"; do
  k=${spec%%:*}; rest=${spec#*:}; v=${rest%%:*}; bpv=${rest#*:}
  raw="$OUT/${k}__${v}.log"
  TURBO_AUTO_ASYMMETRIC=0 timeout 5400 "$B" -m "$M" -f "$P" -ngl 99 \
        -ctk "$k" -ctv "$v" --n-prefix 128 --max-prompts 128 --n-score 128 > "$raw" 2>&1
  line=$(grep -m1 "^SUMMARY" "$raw")
  if [ -z "$line" ]; then
    printf "%-16s %-8s %s\n" "$k/$v" "$bpv" "FAILED: $(grep -m1 -iE "fatal error|GGML_ASSERT|unsupported" "$raw" | cut -c1-58)"
  else
    g(){ echo "$line" | grep -o "$1=[-0-9.]*" | cut -d= -f2; }
    printf "%-16s %-8s %-10s %-10s %-10s %-10s %-10s\n" "$k/$v" "$bpv" \
      "$(g flip_rate)" "$(g mean_KL)" "$(g mean_R)" "$(g cvar95_R)" "$(g frac_Lge1)"
  fi
done
echo
echo "### U5d DONE $(date -Is)"
