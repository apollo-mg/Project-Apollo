#!/usr/bin/env bash
# U5e v2 - LOAD-ONLY KV allocation sweep. Resolves the open ambiguity in
# RESULT_U5CD_PLACEMENT.md finding 4: measured KV buffer sizes showed stock types matching
# source block arithmetic exactly while every turbo type allocated ~+0.5 bpv MORE.
#
#   (a) REAL per-token overhead -> byte delta GROWS with n_ctx, bpv stays inflated
#   (b) FIXED padding/alignment -> byte delta stays CONSTANT, bpv converges to layout
#
# v1 used llama-server, which suppresses the model-load detail lines entirely (22-line log,
# no "MiB" anywhere) so every arm burned its full 300s timeout finding nothing.
# v2 uses frontier-hazard, which prints them, and whose --n-prefix SETS n_ctx (= n_prefix + 8).
# Prompts are ~300 tokens so every prompt is skipped at larger n_prefix - that is fine and
# intended: the KV buffers are allocated at context creation, BEFORE any prompt is processed.
# --max-prompts 1 keeps it to one skip. Exit code will be 2 (0 prompts completed); ignored.
#
# NOTE: frontier-hazard builds TWO contexts - an f16 reference AND the quantized one. The
# f16 reference is the FIRST "KV buffer size" occurrence per device, the arm under test is
# the SECOND. v1 of the U5c analysis initially misread this by using grep -m1.
set -u
B=~/buun_tree_current/build/bin/llama-frontier-hazard
M=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
P=~/hazard_prompts_128.txt
mkdir -p ~/u5e_raw
echo "### U5e v2 LOAD-ONLY KV SIZE - .194 sm_60, buun 02f8581, $(date -Is)"
echo "### n_ctx = n_prefix + 8. Reported size is the QUANT context (2nd occurrence), summed over devices."
printf "%-14s %-8s %-14s %-14s %-12s\n" "K/V" "n_ctx" "quant_MiB" "bytes/token" "bits/value"
for pair in "f16:f16" "q8_0:q8_0" "turbo8:turbo8" "q4_0:q4_0" "turbo4:turbo4" "turbo3:turbo3" "turbo2:turbo2"; do
  k=${pair%%:*}; v=${pair#*:}
  for NP in 504 4088 16376; do
    CTX=$((NP+8))
    log=~/u5e_raw/${k}_${CTX}.log
    TURBO_AUTO_ASYMMETRIC=0 timeout 420 "$B" -m "$M" -f "$P" -ngl 99 \
      -ctk "$k" -ctv "$v" --n-prefix "$NP" --max-prompts 1 --n-score 1 > "$log" 2>&1
    # per device: 1st occurrence = f16 reference, 2nd = quant context under test
    # devices are NOT interleaved: all N devices for the f16 ref, THEN all N for the quant
    # context. Take the second half. (An NR%2==0 parse here would silently mix the two.)
    vals=$(grep "KV buffer size" "$log" | grep -oE "[0-9]+\.[0-9]+")
    nv=$(echo "$vals" | grep -c .)
    tot=$(echo "$vals" | tail -n $((nv/2)) | paste -sd+ | bc 2>/dev/null)
    if [ -z "$tot" ] || [ "$tot" = "0" ]; then
      printf "%-14s %-8s %s\n" "$k/$v" "$CTX" "FAILED: $(grep -m1 -iE 'fatal error|GGML_ASSERT|unsupported|error' $log | cut -c1-52)"
    else
      bpt=$(echo "scale=2; $tot*1048576/$CTX" | bc)
      bpv=$(echo "scale=3; $tot*1048576*8/($CTX*64*2*256*8)" | bc)
      printf "%-14s %-8s %-14s %-14s %-12s\n" "$k/$v" "$CTX" "$tot" "$bpt" "$bpv"
    fi
  done
done
echo "### U5e DONE $(date -Is)"
