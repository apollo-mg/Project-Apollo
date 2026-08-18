#!/usr/bin/env bash
# U5f - THE CLEAN ALLOCATION TEST. Same codec family, pure width difference.
#
# U5d's swap (turbo2/turbo3) survived its confounds but compares two codecs that differ in
# design, rotation-group handling AND kernel dispatch - so it licenses only "turbo3 is worth
# more on V than on K", not "bits belong on V".
#
# q8_0 and q4_0 are both plain block-scalar quant with a per-block ggml_half scale, differing
# ONLY in bits. No FWHT, no turbo kernel, no Q pre-rotation branch (turbo_k_any is false for
# both, so the fattn.cu:2638 path split cannot fire). And U5e/finding-4 showed stock types
# allocate exactly their block layout, so B and C are genuinely equal-cost.
#
#   A q8_0/q8_0 17.0 | B q8_0/q4_0 13.0 | C q4_0/q8_0 13.0 | D q4_0/q4_0 9.0
#
# PRE-REGISTERED (conf 0.55 that the V direction replicates):
#   B vs C same direction as U5d (V favoured) -> allocation claim is real, survives 4 confounds
#   reverses or ties                          -> U5d was a turbo-codec property misread as a law
# RISK: mixed stock KV may abort (upstream refuses K!=V without GGML_CUDA_FA_ALL_QUANTS and
# buun inherits). frontier-hazard uses a single context and no tensor split, so the
# tensor-split aborts do not apply, but the FA type-pair gate might. An abort on B and C means
# the test is unrunnable on this tree - NOT evidence either way.
set -u
B=~/buun_tree_current/build/bin/llama-frontier-hazard
M=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
P=~/hazard_prompts_128.txt
OUT=~/u5f_raw
mkdir -p "$OUT"
while ! grep -q "U5e DONE" ~/u5e.log 2>/dev/null; do sleep 20; done
sleep 10
echo "### U5f CLEAN ALLOCATION - .194 sm_60, buun 02f8581, $(date -Is)"
echo "### 128 prompts, n_prefix 128. B and C: same codec family, pure width, equal cost."
nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader | sed "s/^/###   /"
echo
printf "%-14s %-8s %-10s %-10s %-10s %-10s %-10s\n" "K/V" "tot_bpv" "flip_rate" "mean_KL" "mean_R" "cvar95_R" "frac_L>=1"
for spec in "q8_0:q8_0:17.0" "q8_0:q4_0:13.0" "q4_0:q8_0:13.0" "q4_0:q4_0:9.0"; do
  k=${spec%%:*}; rest=${spec#*:}; v=${rest%%:*}; bpv=${rest#*:}
  raw="$OUT/${k}__${v}.log"
  TURBO_AUTO_ASYMMETRIC=0 timeout 5400 "$B" -m "$M" -f "$P" -ngl 99 \
        -ctk "$k" -ctv "$v" --n-prefix 128 --max-prompts 128 --n-score 128 > "$raw" 2>&1
  line=$(grep -m1 "^SUMMARY" "$raw")
  if [ -z "$line" ]; then
    printf "%-14s %-8s %s\n" "$k/$v" "$bpv" "ABORT/FAIL: $(grep -m1 -iE 'fatal error|GGML_ASSERT|unsupported|not supported' "$raw" | cut -c1-56)"
  else
    g(){ echo "$line" | grep -o "$1=[-0-9.]*" | cut -d= -f2; }
    printf "%-14s %-8s %-10s %-10s %-10s %-10s %-10s\n" "$k/$v" "$bpv" \
      "$(g flip_rate)" "$(g mean_KL)" "$(g mean_R)" "$(g cvar95_R)" "$(g frac_Lge1)"
  fi
done
echo
echo "### U5f DONE $(date -Is)"
