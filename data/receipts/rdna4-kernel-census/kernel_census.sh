#!/usr/bin/env bash
# Which flash_attn_ext_vec instances does a real run actually LAUNCH on gfx1201?
#
# TheTom (#294): "ncols=2 is a shape decode really launches, so a residual there sits on a
# live path, unlike the D=256 one which is a V-side accumulator spill on a shape nothing
# launches." That is an assumption about which template instances reach the GPU. It is
# checkable from outside the build: AMD_LOG_LEVEL=4 prints every dispatch's ShaderName,
# including the template arguments.
#
# ggml_type numbering (fork ggml.h): 1=F16 2=Q4_0 8=Q8_0 43=TURBO2_0 44=TURBO3_0 47=TURBO4_0
#
# No rocprof on this box, so this is the dispatch log rather than a profiler. It gives
# kernel identity and launch count, not timing.
set -u
B=/mnt/TG_2TB/AI/rdna4_f6124e914/build/bin/llama-bench
D128=/mnt/TG_2TB/AI/Models/Llama-3.2-3B-Instruct-BF16.gguf     # D=128, 24/8  GQA 3:1
D256=/mnt/TG_2TB/AI/Models/qwen35/plain-Q8_0.gguf              # D=256, 16/4  GQA 4:1
D256H=/mnt/TG_2TB/AI/Models/"Qwen 3.8"/27B/Qwen3.8-27B-UD-IQ2_M.gguf  # D=256, 24/4 GQA 6:1
T=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/census_tmp.txt

echo "### FA KERNEL LAUNCH CENSUS — gfx1201, build f6124e914  $(date -Is)"
echo "### types: 1=F16 2=Q4_0 8=Q8_0 43=TURBO2 44=TURBO3 47=TURBO4"
echo

census() {
  local label=$1 model=$2 ctk=$3 ctv=$4; shift 4
  printf '%s\n' "--- $label : -ctk $ctk -ctv $ctv $* ---"
  [ -f "$model" ] || { echo "    model missing"; echo; return; }
  TURBO_AUTO_ASYMMETRIC=0 AMD_LOG_LEVEL=4 timeout 400 "$B" -m "$model" -ngl 99 -fa 1 \
      -ctk "$ctk" -ctv "$ctv" -r 1 "$@" > "$T" 2>&1
  grep -o -E "flash_attn_ext_vec<[^>]*>" "$T" | sort | uniq -c | sort -rn | sed 's/^/    /'
  local other
  other=$(grep -o -E "void (flash_attn_ext_tile|flash_attn_ext_mma)[A-Za-z0-9_]*<[^>]*>" "$T" | sort | uniq -c | sort -rn | head -3)
  [ -n "$other" ] && echo "$other" | sed 's/^/    [non-vec] /'
  grep -q "flash_attn_ext" "$T" || echo "    (no FA dispatches seen)"
  echo
}

# Does plain decode launch ncols=2? Vary GQA ratio, which is the packing input.
census "D=128 GQA 3:1  decode"        "$D128"  turbo3 q8_0   -p 0 -n 8
census "D=256 GQA 4:1  decode"        "$D256"  turbo3 q8_0   -p 0 -n 8
census "D=256 GQA 6:1  decode"        "$D256H" turbo3 q8_0   -p 0 -n 8
# Depth should not change ncols, only KV traffic — control.
census "D=128 GQA 3:1  decode @4096"  "$D128"  turbo3 q8_0   -p 0 -n 8 -d 4096
# Prefill takes TILE/MMA, not VEC — scope row.
census "D=128 GQA 3:1  prefill 256"   "$D128"  turbo3 q8_0   -p 256 -n 0
# Symmetric turbo, for comparison with the pair CI flags.
census "D=128 GQA 3:1  turbo3 sym"    "$D128"  turbo3 turbo3 -p 0 -n 8
rm -f "$T"
echo "### CENSUS DONE $(date -Is)"
