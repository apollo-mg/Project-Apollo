#!/usr/bin/env bash
# The clean draft-head experiment: identical body, ONLY blk.64 varies.
#
# The packager A/B on .73 cannot isolate the draft head -- bartowski's and
# unsloth's Q6_K differ in the body too (Q8_0 x120 vs x48), so any difference is
# unattributable. Here we build the files ourselves: one bf16 source, one imatrix,
# one ftype, and a --tensor-type override on blk.64 alone. Bodies are produced by
# the same deterministic path and should come out byte-identical.
#
# Verified before committing the compute:
#   - llama-quant.cpp:185  --tensor-type options are REGEX patterns
#   - llama-quant.cpp:294  tensors with <2 dims are never quantised, so the F32
#                          norms inside blk.64 survive the override untouched
#   - llama-quant.cpp:299  only names ending in 'weight' are quantised
#   => 'blk\.64\.' hits exactly the 8 weight tensors that make up the MTP head.
#
# Head order is deliberate: F16 and Q4_0 first, so even a partial run yields the
# maximum-contrast pair. If that shows nothing, draft-head precision does not
# matter and the intermediate rungs are not worth running.
#
# niced and thread-limited: this box is also the user's desktop.
set -u
BIN=/home/mark/moe-cache-test/src/build-hip/bin
BASE="/mnt/TG_2TB/AI/Models/Qwen 3.8/27B"
SRC="$BASE/bf16"
OUT="$BASE/headlab"
IMAT="$SRC/bartowski-Qwen3.8-27B-imatrix.gguf"
NT=12
mkdir -p "$SRC" "$OUT"

hf () { curl -L -C - --retry 5 --retry-delay 10 --fail -o "$2" \
        "https://huggingface.co/bartowski/Qwen3.8-27B-GGUF/resolve/main/$1"; }

echo "### STAGE 1 fetch source $(date -Is)"
# imatrix is bartowski's published calibration artifact, used as-is and credited.
[ -s "$IMAT" ] || hf "Qwen3.8-27B-imatrix.gguf" "$IMAT" || exit 1
for n in 00001 00002; do
  f="$SRC/Qwen3.8-27B-bf16-$n-of-00002.gguf"
  [ -s "$f" ] || hf "Qwen3.8-27B-bf16/Qwen3.8-27B-bf16-$n-of-00002.gguf" "$f" || exit 1
done
ls -la "$SRC"
LEAD="$SRC/Qwen3.8-27B-bf16-00001-of-00002.gguf"

echo
echo "### STAGE 2 demonstrate the constraint $(date -Is)"
# The receipt INFERRED from source that an IQ3_XXS target on blk.64 must abort,
# because bartowski's imatrix has no entry for it. Show it rather than infer it.
nice -n 10 "$BIN/llama-quantize" --imatrix "$IMAT" "$LEAD" \
    "$OUT/_abort_probe.gguf" IQ3_XXS $NT > "$OUT/abort_probe.log" 2>&1
rc=$?
echo "  exit=$rc"
grep -aiE "Missing importance matrix|bailing out|did not find weights for blk.64" "$OUT/abort_probe.log" | head -5
rm -f "$OUT/_abort_probe.gguf"

echo
echo "### STAGE 3 build the variants $(date -Is)"
for spec in F16:f16 Q4_0:q4_0 IQ4_XS:iq4_xs Q6_K:q6_k; do
  tag=${spec%%:*}; ty=${spec#*:}
  out="$OUT/qwen38-iq3xxs-head$tag.gguf"
  if [ -s "$out" ]; then echo "  $tag already built, skipping"; continue; fi
  echo "  --- head=$tag $(date -Is)"
  nice -n 10 "$BIN/llama-quantize" --imatrix "$IMAT" \
      --tensor-type "blk\.64\.=$ty" \
      "$LEAD" "$out" IQ3_XXS $NT > "$OUT/q_$tag.log" 2>&1 \
    || { echo "  QUANTIZE FAILED for $tag"; tail -5 "$OUT/q_$tag.log"; continue; }
  echo "  built $(stat -c%s "$out") bytes"
done
ls -la "$OUT"
echo "### HEADLAB BUILD DONE $(date -Is)"
