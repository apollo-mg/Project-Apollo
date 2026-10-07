#!/usr/bin/env bash
# PREREG_SPITE_PR23_73 Addendum R4 on .73: round 4 at f85a2a2. Precondition: daily-driver server and wake proxy down.
echo $$ > /tmp/apollo-busy.spite; trap 'rm -f /tmp/apollo-busy.spite' EXIT
cd ~/spite; O=~/spite-test/raw_r4; mkdir -p $O; L=$O/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
M="/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf"; S=./target/release/spite; B=./target/release/spite-bench
BF1=~/spite-test/b_f1; CUDART=/usr/lib/x86_64-linux-gnu/libcudart.so.12
P=( $'Question: What is 17 multiplied by 23?\nAnswer:' $'Question: What is the capital of France?\nAnswer:'
    $'Question: Define photosynthesis in one sentence.\nAnswer:' 'The old man walked to the harbor and' )
pgrep -x llama-server >/dev/null && { log "ABORT: llama-server still running"; exit 1; }
nvidia-smi --query-gpu=index,name,clocks.sm,clocks.applications.graphics,power.limit,memory.used --format=csv > $O/gpu_state_start.csv
log "start; spite $(git rev-parse --short HEAD)"
gen() { python3 -c 'import sys,re; t=open(sys.argv[1],encoding="utf-8").read(); m=re.search(r"stage +: GPU \d+ .*layers \d+\.\.64[^\n]*\n",t); print(repr(t[m.end()+1:] if m else "NO-STAGE-LINE:"+t[-200:]))' "$1"; }
# T6 first (cheap, and tells us early if the batch path is broken)
VK=kernels/qwen/qwen3_5/nvidia/libkernel_qwen_qwen3_5_nvidia.so
timeout 900 python3 tools/verify/verify.py $VK > $O/t6_verify_vendor.txt 2>&1; log "T6 verify.py vendor rc=$? $(grep -E 'PASSED|FAILED' $O/t6_verify_vendor.txt | tail -1) OK=$(grep -c 'OK:' $O/t6_verify_vendor.txt) SKIP=$(grep -c 'SKIP' $O/t6_verify_vendor.txt)"
LD_LIBRARY_PATH=$(dirname $CUDART) timeout 900 python3 tools/verify/verify_batch_cuda.py $VK $CUDART > $O/t6_verify_batch_cuda.txt 2>&1; log "T6 verify_batch_cuda rc=$? $(tail -2 $O/t6_verify_batch_cuda.txt | tr '\n' ' ' | cut -c1-250)"
# T3/T4
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
# T8: spite run --mtp on the 4 prompts (text vs plain A), then spite-bench --mtp at draft 1/2/3
for i in 0 1 2 3; do f=$O/t8_run_mtp_p$((i+1))
  timeout 900 $S run -m "$M" --card TESLA_P100 --device cuda --ctx 8192 --temperature 0 --max-tokens 128 --mtp -p "${P[$i]}" > $f.out 2> $f.err
  rc=$?; gen $f.out > $f.gen; cmp -s $f.gen $O/t3_p$((i+1))_A.gen && same=text-same-as-plain || same=TEXT-DIFFERS
  log "T8 run --mtp p$((i+1)) rc=$rc $same $(grep -i -E 'generate|accept|draft' $f.err | tr '\n' ' ' | cut -c1-220)"
done
for k in 1 2 3; do
  timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --mtp --draft-tokens $k --json > $O/t8_bench_mtp_k$k.json 2> $O/t8_bench_mtp_k$k.err
  log "T8 spite-bench --mtp --draft-tokens $k rc=$? $(tr -d '\n' < $O/t8_bench_mtp_k$k.json | cut -c1-420) $(grep -i error $O/t8_bench_mtp_k$k.err | tail -1 | cut -c1-200)"
done
# T7 prefill before/after (512-token padded prompt), then defaults after
timeout 1800 $BF1/spite-bench --model "$M" --card TESLA_P100 --device cuda --kernels-dir $BF1/kernels --n-prompt 512 --n-tokens 32 --n-runs 3 --json > $O/t7_prefill_before.json 2> $O/t7_prefill_before.err; log "T7 prefill BEFORE (f1cc494) rc=$? $(tr -d '\n' < $O/t7_prefill_before.json | cut -c1-400)"
timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --n-prompt 512 --n-tokens 32 --n-runs 3 --json > $O/t7_prefill_after.json 2> $O/t7_prefill_after.err; log "T7 prefill AFTER (f85a2a2) rc=$? $(tr -d '\n' < $O/t7_prefill_after.json | cut -c1-400)"
timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --json > $O/t7_bench.json 2> $O/t7_bench.err; log "T7 spite-bench defaults rc=$? $(tr -d '\n' < $O/t7_bench.json | cut -c1-400)"
nvidia-smi --query-gpu=index,clocks.sm,clocks.applications.graphics --format=csv,noheader > $O/gpu_state_end.csv
log TESTS_DONE
