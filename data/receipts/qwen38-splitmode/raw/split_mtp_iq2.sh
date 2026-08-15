#!/usr/bin/env bash
# Split-mode x MTP ladder on UD-IQ2_M -- same six cells as the IQ3_XXS run.
#
# Every arm tag is prefixed `iq2_` so nothing collides with the IQ3_XXS ladder's
# pkg_*.json in the same directory. (A sed-based clone of that script silently
# left half the tags unprefixed, which would have overwritten six IQ3 result
# files. Written out explicitly instead.)
#
# What makes IQ2 worth a second ladder rather than a curiosity: unsloth spends
# MORE absolute bits on the draft head at the lower tier -- 205.61 MiB against
# IQ3_XXS's 194.94 MiB -- while the body drops from 11.10 to 9.61 GiB. So the
# draft budget is near-constant and the target is substantially worse. If
# acceptance falls here it is attributable to the target, not the draft.
#
# The heads are NOT identical, and an earlier framing that said so was wrong:
# the type histograms match (IQ4_XS x5 + IQ3_S x3) but the per-tensor assignment
# differs -- attn_q is IQ4_XS at IQ3_XXS and IQ3_S at IQ2_M, while ffn_down and
# ffn_up swap the other way. A matching histogram is not a matching recipe.
set -u
D=/home/mark/mtp73
BIN=/home/mark/buun_vbr/build/bin/llama-server
M=/home/mark/models/Qwen3.8-27B-UD-IQ2_M.gguf
export LD_LIBRARY_PATH="$(dirname $BIN):${LD_LIBRARY_PATH:-}"
export REPS=2
SPEC="--spec-type draft-mtp --spec-draft-n-max 3"

for f in "$M" "$BIN" "$D/mtp_pkg_ab.py"; do
  [ -e "$f" ] || { echo "ABORT: missing $f"; exit 1; }
done

serve () {   # $1 tag, $2 split flags, $3 spec flags, $4 env prefix
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

SOLO="CUDA_VISIBLE_DEVICES=0"
LAY="-sm layer -ts 1,1"
TEN="-sm tensor"

# forward half
arm iq2_sing_off_1  ""     ""      "$SOLO" 0
arm iq2_sing_on_1   ""     "$SPEC" "$SOLO" 1
arm iq2_layer_off_1 "$LAY" ""      ""      0
arm iq2_layer_on_1  "$LAY" "$SPEC" ""      1
arm iq2_tens_off_1  "$TEN" ""      ""      0
arm iq2_tens_on_1   "$TEN" "$SPEC" ""      1
# reversed half
arm iq2_tens_on_2   "$TEN" "$SPEC" ""      1
arm iq2_tens_off_2  "$TEN" ""      ""      0
arm iq2_layer_on_2  "$LAY" "$SPEC" ""      1
arm iq2_layer_off_2 "$LAY" ""      ""      0
arm iq2_sing_on_2   ""     "$SPEC" "$SOLO" 1
arm iq2_sing_off_2  ""     ""      "$SOLO" 0

pkill -x llama-server 2>/dev/null
echo "### IQ2 SPLIT x MTP DONE $(date -Is)"
