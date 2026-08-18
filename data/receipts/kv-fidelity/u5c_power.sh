#!/usr/bin/env bash
# U5c - matched-budget SYMMETRY test + power, on buun 02f8581.
#
# Two questions at once:
#  (a) buun aliasing claim: q8_0->turbo8, q4_0->turbo4 "costs users nothing"
#  (b) Mark/h4rm0n1c: turbo codecs perform badly SYMMETRIC due to the rotation math.
#      turbo8 is "no QJL" + "FWHT outlier suppression" => the rotation is DETERMINISTIC,
#      so symmetric K/V share an identical transform and their errors can correlate.
#
# Design: two tiers, each 4 arms at near-matched total bits/value.
#   8-bit tier  q8_0/q8_0 17.00 | q8_0/turbo8 16.625 | turbo8/q8_0 16.625 | turbo8/turbo8 16.25
#   4-bit tier  q4_0/q4_0  9.00 | q4_0/turbo4  8.625 | turbo4/q4_0  8.625 | turbo4/turbo4  8.25
#   (q8_0 8.5 bpv=34B/32, turbo8 8.125=130B/128, q4_0 4.5=18B/32, turbo4 4.125=66B/128)
#
# PRE-REGISTERED, before results:
#   BIT-BUDGET hypothesis -> R monotone in total bits; mixed arms land BETWEEN the symmetrics.
#   SYMMETRY  hypothesis -> mixed arms dip BELOW that interpolation line.
#   P1 8-bit tier shows a symmetry dip    conf 0.50
#   P2 4-bit tier shows a symmetry dip    conf 0.60  (larger errors, more headroom to resolve)
#   P3 f16 control exact null             conf 0.97
#
# U5b answered at n=16 PROMPTS - frontier-hazard means divide by n_done (prompt count),
# not tokens - too few to resolve. 128 prompts here, an exact superset of U5b (first 16
# bytes-identical), so U5b is the head of this run.
# Keeps FULL per-arm output: KV buffer size, q8_0-fallback warning, cvar95_R, DEPTH bands.
set -u
B=~/buun_tree_current/build/bin/llama-frontier-hazard
M=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
P=~/hazard_prompts_128.txt
OUT=~/u5c_raw
mkdir -p "$OUT"
echo "### U5c MATCHED-BUDGET SYMMETRY - .194 sm_60, buun 02f8581, $(basename $M)  $(date -Is)"
echo "### 128 wikitext prompts (exact superset of U5b 16), n_prefix 128, n_score 128"
echo "### GPU state:"
nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader | sed "s/^/###   /"
echo
printf "%-16s %-8s %-10s %-10s %-10s %-10s %-10s %-10s\n" "K/V" "tot_bpv" "flip_rate" "mean_KL" "mean_R" "cvar95_R" "mean_L" "frac_L>=1"
for spec in "f16:f16:32.00" \
            "q8_0:q8_0:17.00" "q8_0:turbo8:16.625" "turbo8:q8_0:16.625" "turbo8:turbo8:16.25" \
            "q4_0:q4_0:9.00"  "q4_0:turbo4:8.625"  "turbo4:q4_0:8.625"  "turbo4:turbo4:8.25"; do
  k=${spec%%:*}; rest=${spec#*:}; v=${rest%%:*}; bpv=${rest#*:}
  raw="$OUT/${k}__${v}.log"
  TURBO_AUTO_ASYMMETRIC=0 timeout 5400 "$B" -m "$M" -f "$P" -ngl 99 \
        -ctk "$k" -ctv "$v" --n-prefix 128 --max-prompts 128 --n-score 128 > "$raw" 2>&1
  line=$(grep -m1 "^SUMMARY" "$raw")
  if [ -z "$line" ]; then
    printf "%-16s %-8s %s\n" "$k/$v" "$bpv" "FAILED: $(grep -m1 -iE "error|abort|ASSERT|unsupported" "$raw" | cut -c1-58)"
  else
    g(){ echo "$line" | grep -o "$1=[-0-9.]*" | cut -d= -f2; }
    printf "%-16s %-8s %-10s %-10s %-10s %-10s %-10s %-10s\n" "$k/$v" "$bpv" \
      "$(g flip_rate)" "$(g mean_KL)" "$(g mean_R)" "$(g cvar95_R)" "$(g mean_L)" "$(g frac_Lge1)"
  fi
done
echo
echo "### KV buffer size per arm (empirical check on the bits arithmetic):"
for f in "$OUT"/*.log; do
  printf "###   %-18s %s\n" "$(basename "$f" .log)" "$(grep -h "KV buffer size" "$f" | tr -s " " | paste -sd" " | cut -c1-80)"
done
echo "### q8_0 fallback warnings (must be none):"
grep -l "falling back to q8_0" "$OUT"/*.log 2>/dev/null | sed "s/^/###   FIRED: /" || echo "###   none"
echo "### U5c DONE $(date -Is)"
