#!/usr/bin/env bash
# U5 — the first FIDELITY numbers of this campaign.
#
# Every "clean" verdict on the compatibility map means *not degenerate*: the collapse
# detector fires on 512 identical characters and sees nothing else. It has never been able
# to distinguish "faithful" from "subtly wrong". That caveat is stamped on eight receipts
# and on the map shared with Tom and buun.
#
# buun's own frontier-hazard closes it. Teacher-forced: a reference f16/f16 context and a
# quantized context decode the SAME real wikitext tokens, and at each scored position it
# reports top-1 flip rate, KL, decision-danger R = KL/(0.5*margin^2), and margin erosion L.
#
# Note --n-ubatch 8: frontier-hazard prefills n_prefix tokens, and on gfx1201 any quantized
# KV with Q->ne[1] > 8 aborts in the TILE/MMA path (RESULT_LAUNCH_CENSUS.md). 8 keeps every
# ubatch inside VEC. Found this morning; it would otherwise have killed every arm below.
#
# f16/f16 is the exact-anchor control and MUST come back all zeros.
set -u
B=/mnt/TG_2TB/AI/tq295/src/build/bin/llama-frontier-hazard
M=/mnt/TG_2TB/AI/Models/qwen35/plain-Q8_0.gguf     # Qwen3.5-9B Q8_0, D=256, GQA 4:1
P=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/hazard_prompts.txt
echo "### U5 FIDELITY — gfx1201, $(basename $M), teacher-forced vs f16/f16  $(date -Is)"
echo "### tool: buun-quality-bench frontier-hazard | 16 prompts, n_prefix 128, n_score 128"
echo
printf '%-16s %-10s %-10s %-10s %-10s %-10s\n' "K/V" "flip_rate" "mean_KL" "mean_R" "mean_L" "frac_L>=1"
for pair in "f16:f16" "q8_0:q8_0" "q4_0:q4_0" "turbo2:turbo2" "turbo3:turbo3" "turbo4:turbo4" "q8_0:turbo4" "turbo3:q8_0"; do
  k=${pair%%:*}; v=${pair#*:}
  out=$(TURBO_AUTO_ASYMMETRIC=0 timeout 900 "$B" -m "$M" -f "$P" -ngl 99 \
        -ctk "$k" -ctv "$v" --n-prefix 128 --max-prompts 16 --n-score 128 --n-ubatch 8 2>&1)
  line=$(echo "$out" | grep -m1 "^SUMMARY")
  if [ -z "$line" ]; then
    printf '%-16s %s\n' "$k/$v" "FAILED: $(echo "$out" | grep -m1 -iE 'error|abort|assert' | cut -c1-60)"
  else
    printf '%-16s %-10s %-10s %-10s %-10s %-10s\n' "$k/$v" \
      "$(echo "$line" | grep -o 'flip_rate=[0-9.]*' | cut -d= -f2)" \
      "$(echo "$line" | grep -o 'mean_KL=[0-9.]*'   | cut -d= -f2)" \
      "$(echo "$line" | grep -o 'mean_R=[0-9.]*'    | cut -d= -f2)" \
      "$(echo "$line" | grep -o 'mean_L=[-0-9.]*'   | cut -d= -f2)" \
      "$(echo "$line" | grep -o 'frac_Lge1=[0-9.]*' | cut -d= -f2)"
  fi
done
echo
echo "### U5 DONE $(date -Is)"
