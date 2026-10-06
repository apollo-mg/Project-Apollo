#!/usr/bin/env bash
# PREREG_SPITE_PR23_73 Addendum R on .73: the T3/T4/T6/T7/T8 rows at PR head 06e44a0. llama.cpp outputs are reused
# from the first pass (same file and server config). Precondition: daily-driver server and wake proxy down.
echo $$ > /tmp/apollo-busy.spite; trap 'rm -f /tmp/apollo-busy.spite' EXIT
cd ~/spite; O=~/spite-test/raw_r; mkdir -p $O; L=$O/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
M="/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf"; S=./target/release/spite; B=./target/release/spite-bench
P=( $'Question: What is 17 multiplied by 23?\nAnswer:' $'Question: What is the capital of France?\nAnswer:'
    $'Question: Define photosynthesis in one sentence.\nAnswer:' 'The old man walked to the harbor and' )
pgrep -x llama-server >/dev/null && { log "ABORT: llama-server still running"; exit 1; }
nvidia-smi --query-gpu=index,name,clocks.sm,clocks.applications.graphics,power.limit,memory.used --format=csv > $O/gpu_state_start.csv
log "start; spite $(git rev-parse --short HEAD)"
gen() { python3 -c 'import sys,re; t=open(sys.argv[1],encoding="utf-8").read(); m=re.search(r"stage +: GPU \d+ .*layers \d+\.\.64[^\n]*\n",t); print(repr(t[m.end()+1:] if m else "NO-STAGE-LINE:"+t[-200:]))' "$1"; }
for i in 0 1 2 3; do
  for cfg in A B C; do
    X=""; [ $cfg = B ] && X="--gpus 1,0"
    f=$O/t3_p$((i+1))_$cfg
    timeout 900 $S run -m "$M" --card TESLA_P100 --device cuda --ctx 8192 --temperature 0 --max-tokens 128 $X -p "${P[$i]}" > $f.out 2> $f.err
    rc=$?; log "T3/T4 p$((i+1)) $cfg rc=$rc stage-lines=$(cat $f.out $f.err | grep -c 'stage *:') $(grep generate $f.err)"
    [ $rc != 0 ] && log "  err: $(tail -3 $f.err | tr '\n' ' ' | cut -c1-300)"
    gen $f.out > $f.gen
  done
done
for i in 1 2 3 4; do
  cmp -s $O/t3_p${i}_A.gen $O/t3_p${i}_B.gen && ab=same || ab=DIFF; cmp -s $O/t3_p${i}_A.gen $O/t3_p${i}_C.gen && ac=same || ac=DIFF
  log "T4 p$i (generated text only): A vs B(reversed) $ab, A vs C(repeat) $ac"
done
timeout 900 $S run -m "$M" --card TESLA_P100 --device cuda --ctx 8192 --temperature 0 --max-tokens 128 --mtp -p "${P[3]}" > $O/t8_mtp.out 2> $O/t8_mtp.err
gen $O/t8_mtp.out > $O/t8_mtp.gen; log "T8 run --mtp rc=$? $(grep generate $O/t8_mtp.err) $(cmp -s $O/t8_mtp.gen $O/t3_p4_A.gen && echo text-same-as-A || echo text-differs-from-A)"
timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --json > $O/t7_bench.json 2> $O/t7_bench.err; log "T7 spite-bench rc=$? $(tr -d '\n' < $O/t7_bench.json | cut -c1-400)"
timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --mtp --json > $O/t8_bench_mtp.json 2> $O/t8_bench_mtp.err; log "T8 spite-bench --mtp rc=$? $(tr -d '\n' < $O/t8_bench_mtp.json | cut -c1-300) $(grep -i -E 'error' $O/t8_bench_mtp.err | tail -1 | cut -c1-250)"
timeout 900 python3 tools/verify/verify.py kernels/qwen/qwen3_5/nvidia/libkernel_qwen_qwen3_5_nvidia.so > $O/t6_verify_vendor.txt 2>&1; log "T6 verify vendor rc=$? $(grep -E 'PASSED|FAILED' $O/t6_verify_vendor.txt | tail -1) OK=$(grep -c 'OK:' $O/t6_verify_vendor.txt) SKIP=$(grep -c 'SKIP' $O/t6_verify_vendor.txt)"
timeout 600 python3 tools/verify/verify.py kernels/qwen/qwen3_5/nvidia/sm_60/tesla_p100/libkernel_qwen_qwen3_5_nvidia_sm_60_tesla_p100.so > $O/t6_verify_card.txt 2>&1; log "T6 verify card rc=$? $(grep -E 'PASSED|FAILED' $O/t6_verify_card.txt | tail -1)"
nvidia-smi --query-gpu=index,clocks.sm,clocks.applications.graphics --format=csv,noheader > $O/gpu_state_end.csv
log TESTS_DONE
