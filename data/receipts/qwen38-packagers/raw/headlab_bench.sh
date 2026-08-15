#!/usr/bin/env bash
# Bench the head-isolation variants on RDNA4, then sweep draft depth.
#
# Stage A -- the experiment: 4 head variants x {MTP off, on} at n-max 3.
#   MTP-off is the control. The bodies are identical by construction, so if
#   MTP-off throughput moves between variants, something other than the head
#   changed and Stage A is unreadable (H3 in the prereg).
#
# Stage B -- draft depth. The prereg listed single-depth as a limit: it cannot
#   separate "draft step costs too much" from "verify batch pays off", because
#   both scale with depth. Sweeping n-max on one variant gives the curve.
#
# Stage C -- comparability. @coffeecup2020 published draft acceptance 0.849 and
#   ~2.70 tokens/step for Qwen3.8-27B TQ3_4S on a 3090, using n-max 2, n-min 1,
#   p-min 0.0 and backend sampling OFF. Acceptance is accepted/drafted, and
#   per-position acceptance falls with depth, so his n-max 2 figure is NOT
#   comparable to our n-max 3 arms. This cell reproduces his flag set exactly so
#   there is one apples-to-apples number. Different quant (TQ3_4S vs IQ3_XXS),
#   different GPU, different fork -- so even matched, it is a weak comparison,
#   but a matched weak comparison beats an unmatched one.
#   (In this build p-min already defaults to 0.0, so that flag of his is a no-op.
#    n-min 0->1 and backend sampling on->off are the real differences.)
set -u
BIN=/home/mark/moe-cache-test/src/build-hip/bin/llama-server
OUT="/mnt/TG_2TB/AI/Models/Qwen 3.8/27B/headlab"
H=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
export REPS=2

serve () {   # $1 tag, $2 model, $3 spec flags
  pgrep -x llama-server >/dev/null && { pkill -x llama-server; sleep 5; }
  setsid nohup "$BIN" -m "$2" -ngl 999 -c 8192 -fa on -np 1 $3 \
      --port 8082 --host 127.0.0.1 > "$OUT/srv_$1.log" 2>&1 < /dev/null &
  for i in $(seq 1 150); do
    curl -s http://127.0.0.1:8082/health 2>/dev/null | grep -q '"ok"' && return 0
    sleep 4
  done
  echo "  SERVER FAILED ($1)"; grep -aiE "error|out of memory|failed" "$OUT/srv_$1.log" | head -4
  return 1
}
arm () {     # $1 tag, $2 model, $3 spec flags, $4 expect_draft
  echo "### $1  $(date -Is)"
  serve "$1" "$2" "$3" || return 1
  grep -aoE "\[spec\][^$]*" "$OUT/srv_$1.log" | head -2
  EXPECT_DRAFT=$4 python3 "$H/headlab_ab.py" "$1" || echo "### ARM $1 NONZERO EXIT"
}

SPEC3="--spec-type draft-mtp --spec-draft-n-max 3"
echo "===== STAGE A: head variants ====="
for tag in F16 Q4_0 IQ4_XS Q6_K; do
  m="$OUT/qwen38-iq3xxs-head$tag.gguf"
  [ -s "$m" ] || { echo "  (no $tag variant built, skipping)"; continue; }
  arm "hl_${tag}_off" "$m" ""       0
  arm "hl_${tag}_on"  "$m" "$SPEC3" 1
done

echo
echo "===== STAGE B: draft depth sweep (F16 head) ====="
M16="$OUT/qwen38-iq3xxs-headF16.gguf"
if [ -s "$M16" ]; then
  for n in 1 2 4 6; do
    arm "hl_depth$n" "$M16" "--spec-type draft-mtp --spec-draft-n-max $n" 1
  done
fi

echo
echo "===== STAGE C: @coffeecup2020 flag set, for comparability ====="
for tag in F16 Q4_0; do
  m="$OUT/qwen38-iq3xxs-head$tag.gguf"
  [ -s "$m" ] && arm "hl_cc_$tag" "$m" \
     "--spec-type draft-mtp --spec-draft-n-min 1 --spec-draft-n-max 2 --spec-draft-p-min 0.0 --no-spec-draft-backend-sampling" 1
done

pkill -x llama-server 2>/dev/null
echo "### HEADLAB BENCH DONE $(date -Is)"
