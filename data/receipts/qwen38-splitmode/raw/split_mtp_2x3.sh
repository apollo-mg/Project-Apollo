#!/usr/bin/env bash
# Does MTP compose with tensor split? {single, layer, tensor} x {MTP off, on}.
#
# Mechanism is genuinely ambiguous, which is why this is worth running:
#   - the MTP DRAFT step is one small layer. Under tensor split its ops are split
#     across both cards with an all-reduce each -- a bad compute:comm ratio for an
#     op that size. Predicts MTP pays LESS under tensor split.
#   - the VERIFY step evaluates 3-4 tokens at once, i.e. more compute per
#     all-reduce than single-token decode. Predicts the opposite.
#
# UD-IQ3_XXS (11.09 GiB) fits on ONE P100, so the no-split row is available and
# gives the MTP multiplier with no interconnect involved at all. That is the
# reference the other two rows are read against.
#
# Same acceptance-capturing harness as the packager A/B. Acceptance doubles as a
# CONTROL here: it is a property of the draft/target pair, not of placement, so
# it should be near-constant across split modes. If it moves a lot, the split is
# perturbing the numerics enough to change draft agreement -- which we already
# know it does at temp 0 (qwen38-splitmode Finding 4) and would itself be a result.
set -u
D=/home/mark/mtp73
BIN=/home/mark/buun_vbr/build/bin/llama-server
M=/home/mark/models/Qwen3.8-27B-UD-IQ3_XXS.gguf
export LD_LIBRARY_PATH="$(dirname $BIN):${LD_LIBRARY_PATH:-}"
export REPS=2
SPEC="--spec-type draft-mtp --spec-draft-n-max 3"

for f in "$M" "$BIN" "$D/mtp_pkg_ab.py"; do
  [ -e "$f" ] || { echo "ABORT: missing $f"; exit 1; }
done

serve () {   # $1 = tag, $2 = split flags, $3 = spec flags, $4 = env prefix
  pgrep -x llama-server >/dev/null && { pkill -x llama-server; sleep 6; }
  env $4 setsid nohup "$BIN" -m "$M" -ngl 999 -c 8192 -fa on -np 1 $2 $3 \
      --port 8082 --host 127.0.0.1 > "$D/srv_$1.log" 2>&1 < /dev/null &
  for i in $(seq 1 200); do
    curl -s http://127.0.0.1:8082/health 2>/dev/null | grep -q '"ok"' && return 0
    sleep 5
  done
  echo "  SERVER FAILED ($1)"; grep -aiE "error|not implemented|out of memory" "$D/srv_$1.log" | head -4
  return 1
}

arm () {     # $1 tag, $2 split, $3 spec, $4 env, $5 expect_draft
  echo "### $1  $(date -Is)"
  serve "$1" "$2" "$3" "$4" || return 1
  grep -aoE "\[spec\][^$]*" "$D/srv_$1.log" | head -2
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
  EXPECT_DRAFT=$5 python3 $D/mtp_pkg_ab.py "$1" || echo "### ARM $1 NONZERO EXIT"
}

nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader

# Palindrome over all six cells: each appears once in each half, so split mode and
# MTP state are both balanced against position.
run_all () {
  arm "sing_off_$1"  ""                  ""      "CUDA_VISIBLE_DEVICES=0" 0
  arm "sing_on_$1"   ""                  "$SPEC" "CUDA_VISIBLE_DEVICES=0" 1
  arm "layer_off_$1" "-sm layer -ts 1,1" ""      "" 0
  arm "layer_on_$1"  "-sm layer -ts 1,1" "$SPEC" "" 1
  arm "tens_off_$1"  "-sm tensor"        ""      "" 0
  arm "tens_on_$1"   "-sm tensor"        "$SPEC" "" 1
}
run_all 1
# reversed second half
arm "tens_on_2"   "-sm tensor"        "$SPEC" "" 1
arm "tens_off_2"  "-sm tensor"        ""      "" 0
arm "layer_on_2"  "-sm layer -ts 1,1" "$SPEC" "" 1
arm "layer_off_2" "-sm layer -ts 1,1" ""      "" 0
arm "sing_on_2"   ""                  "$SPEC" "CUDA_VISIBLE_DEVICES=0" 1
arm "sing_off_2"  ""                  ""      "CUDA_VISIBLE_DEVICES=0" 0

pkill -x llama-server 2>/dev/null
echo "### SPLIT x MTP DONE $(date -Is)"
