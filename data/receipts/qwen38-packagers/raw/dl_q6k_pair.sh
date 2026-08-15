#!/usr/bin/env bash
# Pull both packagers' Q6_K for the MTP draft-head A/B.
#
# Same label, same base model, ~same size -- the variable under test is the
# 8-tensor MTP head: bartowski ships it Q4_0, unsloth ships it Q6_K x7 + Q8_0 x1.
# Neither packager's imatrix covers blk.64, so both heads are quantised blind;
# this measures what that costs in draft acceptance.
#
# Sequential, not parallel: predictable progress and no disk contention on a box
# that is about to run timed benchmarks off the same spindle.
set -u
D=/home/mark/models
mkdir -p "$D"
get () {   # $1 = owner, $2 = local name
  local url="https://huggingface.co/$1/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-Q6_K.gguf"
  echo "### $(date -Is) fetching $1 -> $2"
  # -C - resumes a partial file; --retry rides out HF hiccups on a 21 GiB pull
  curl -L -C - --retry 5 --retry-delay 10 --fail -o "$D/$2" "$url" \
      || { echo "### FAILED $1"; return 1; }
  echo "### $(date -Is) done $2  $(stat -c%s "$D/$2") bytes"
}
df -h / | tail -1
get bartowski bartowski-Qwen3.8-27B-Q6_K.gguf
get unsloth   unsloth-Qwen3.8-27B-Q6_K.gguf
echo "### hashing for provenance"
for f in bartowski-Qwen3.8-27B-Q6_K.gguf unsloth-Qwen3.8-27B-Q6_K.gguf; do
  [ -f "$D/$f" ] && echo "$(sha256sum "$D/$f")"
done
df -h / | tail -1
echo "### DOWNLOADS DONE"
