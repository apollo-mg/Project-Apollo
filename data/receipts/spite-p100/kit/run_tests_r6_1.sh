#!/usr/bin/env bash
# Deviation R6-1 on .73: --mtp text vs plain at K=1 on the 27B; 2B unsplit vs forced split. Waits for the R6 runner.
while kill -0 "$(cat ~/spite-test/run_tests_r6.pid)" 2>/dev/null; do sleep 15; done
echo $$ > /tmp/apollo-busy.spite; trap 'rm -f /tmp/apollo-busy.spite' EXIT
cd ~/spite; O=~/spite-test/raw_r6; L=$O/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
M="/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf"; M2=~/spite-test/models/Qwen3.5-2B-Q6_K.gguf; S=./target/release/spite
PR="The history of the Roman Republic begins with the overthrow of the monarchy."
gen() { python3 -c 'import sys,re; t=open(sys.argv[1],encoding="utf-8").read(); m=re.search(r"device +:[^\n]*\n(?:  stage[^\n]*\n)*\n",t); print(repr(t[m.end():] if m else "NO-DEVICE-LINE:"+t[-200:]))' "$1"; }
pgrep -x llama-server >/dev/null && { log "R6-1 ABORT: llama-server still running"; exit 1; }
log "R6-1 start"
run() { local name=$1 model=$2; shift 2; local f=$O/r61_$name
  timeout 900 $S run -m "$model" --card TESLA_P100 --device cuda --ctx 8192 --temperature 0 --max-tokens 128 "$@" -p "$PR" > $f.out 2> $f.err
  log "R6-1 $name rc=$? stages=$(grep -c 'stage *:' $f.out) $(grep generate $f.err)"; gen $f.out > $f.gen; }
run q27_mtp_k1 "$M" --mtp --draft-tokens 1
cmp -s $O/r61_q27_mtp_k1.gen $O/roman_run_plain.gen && log "R6-1a 27B --mtp K=1: text same as plain" || log "R6-1a 27B --mtp K=1: TEXT DIFFERS"
run q2b_plain "$M2"
run q2b_mtp "$M2" --mtp
run q2b_mtp_k1 "$M2" --mtp --draft-tokens 1
run q2b_split_plain "$M2" --gpus 0,1 --layer-split 12,12
run q2b_split_mtp "$M2" --gpus 0,1 --layer-split 12,12 --mtp
for x in mtp mtp_k1; do cmp -s $O/r61_q2b_$x.gen $O/r61_q2b_plain.gen && log "R6-1b 2B unsplit --$x: text same as plain" || log "R6-1b 2B unsplit --$x: TEXT DIFFERS"; done
cmp -s $O/r61_q2b_split_plain.gen $O/r61_q2b_plain.gen && log "R6-1c 2B split plain = unsplit plain" || log "R6-1c 2B split plain DIFFERS from unsplit"
cmp -s $O/r61_q2b_split_mtp.gen $O/r61_q2b_split_plain.gen && log "R6-1 2B split --mtp: text same as split plain" || log "R6-1 2B split --mtp: TEXT DIFFERS from split plain"
log R61_DONE
