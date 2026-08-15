#!/usr/bin/env bash
# MTP draft-head A/B: bartowski Q4_0 head vs unsloth Q6_K head, same Q6_K label.
#
# Ordering is a palindrome -- bart_off, bart_on, unsl_off, unsl_on, then the
# reverse -- so every cell appears once in each half. This fleet has produced
# 2-3.9x position artifacts on identical configs, and a straight A,A,B,B would
# confound packager with position.
#
# -sm layer -ts 1,1, NOT -sm tensor. Tensor split is 1.63x faster here and it is
# tempting, but its interaction with speculative decoding is untested on this
# node, and this experiment is about the draft head. Layer split is the config
# the earlier .73 MTP result used, so these numbers stay comparable to it.
#
# Per-arm server logs. The previous harness wrote every arm to one file and the
# last arm overwrote the engagement evidence for all the others.
set -u
D=/home/mark/mtp73
M=/home/mark/models
BIN=/home/mark/buun_vbr/build/bin/llama-server
export LD_LIBRARY_PATH="$(dirname $BIN):${LD_LIBRARY_PATH:-}"
export REPS=2
SPEC="--spec-type draft-mtp --spec-draft-n-max 3"

BART=$M/bartowski-Qwen3.8-27B-Q6_K.gguf
UNSL=$M/unsloth-Qwen3.8-27B-Q6_K.gguf
for f in "$BART" "$UNSL" "$BIN" "$D/mtp_pkg_ab.py"; do
  [ -e "$f" ] || { echo "ABORT: missing $f"; exit 1; }
done

serve () {   # $1 = arm tag, $2 = model, $3 = extra flags
  pgrep -x llama-server >/dev/null && { pkill -x llama-server; sleep 6; }
  setsid nohup "$BIN" -m "$2" -ngl 999 -c 8192 -fa on -np 1 -sm layer -ts 1,1 $3 \
      --port 8082 --host 127.0.0.1 > "$D/srv_$1.log" 2>&1 < /dev/null &
  for i in $(seq 1 240); do
    curl -s http://127.0.0.1:8082/health 2>/dev/null | grep -q '"ok"' && return 0
    sleep 5
  done
  echo "  SERVER FAILED ($1)"
  grep -aiE "error|out of memory|failed|not implemented" "$D/srv_$1.log" | head -5
  return 1
}

arm () {     # $1 = tag, $2 = model, $3 = flags, $4 = expect draft (0/1)
  echo "### $1  $(date -Is)"
  serve "$1" "$2" "$3" || return 1
  grep -aoE "\[spec\][^$]*" "$D/srv_$1.log" | head -2      # engagement, per arm
  EXPECT_DRAFT=$4 python3 $D/mtp_pkg_ab.py "$1" || echo "### ARM $1 NONZERO EXIT"
}

nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader

# --- preflight: prove draft stats are actually visible before burning 90 min ---
echo "### PREFLIGHT: do draft_n / draft_n_accepted come back?"
if serve preflight "$BART" "$SPEC"; then
  PF=$(curl -s http://127.0.0.1:8082/v1/chat/completions -H 'Content-Type: application/json' \
       -d '{"messages":[{"role":"user","content":"Write the numbers 1 to 40, one per line."}],
            "temperature":0,"top_k":1,"seed":1234,"n_predict":120,"timings_per_token":true}')
  echo "$PF" | python3 -c "
import json,sys
d=json.load(sys.stdin); t=d.get('timings') or {}
print('  timings keys:', sorted(t))
dn,da=t.get('draft_n'),t.get('draft_n_accepted')
print(f'  draft_n={dn} accepted={da}')
if dn is None:
    print('  PREFLIGHT FAIL: server does not report draft stats on this endpoint')
    sys.exit(3)
print(f'  PREFLIGHT OK: acceptance {100*da/dn:.1f}%')
" || { echo "### ABORT: cannot measure acceptance, not running blind"; pkill -x llama-server; exit 3; }
else
  echo "### ABORT: preflight server failed"; exit 1
fi

arm bart_off_1 "$BART" ""      0
arm bart_on_1  "$BART" "$SPEC" 1
arm unsl_off_1 "$UNSL" ""      0
arm unsl_on_1  "$UNSL" "$SPEC" 1
arm unsl_on_2  "$UNSL" "$SPEC" 1
arm unsl_off_2 "$UNSL" ""      0
arm bart_on_2  "$BART" "$SPEC" 1
arm bart_off_2 "$BART" ""      0

pkill -x llama-server 2>/dev/null
echo "### PKG MTP AB DONE $(date -Is)"
