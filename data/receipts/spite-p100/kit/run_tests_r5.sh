#!/usr/bin/env bash
# PREREG_SPITE_PR23_73 Addendum R5 on .73: round 5 at 6e708fb (= caa2d72 + a test comment), the author's list.
# Precondition: daily-driver server and wake proxy down.
echo $$ > /tmp/apollo-busy.spite; trap 'rm -f /tmp/apollo-busy.spite; kill $SMI 2>/dev/null' EXIT
cd ~/spite; O=~/spite-test/raw_r5; mkdir -p $O; L=$O/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
M="/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf"; B=./target/release/spite-bench; BF1=~/spite-test/b_f1
CUDART=/usr/lib/x86_64-linux-gnu/libcudart.so.12; VK=kernels/qwen/qwen3_5/nvidia/libkernel_qwen_qwen3_5_nvidia.so
BB() { timeout 1800 "$B" --model "$M" --card TESLA_P100 --device cuda "$@"; }
pgrep -x llama-server >/dev/null && { log "ABORT: llama-server still running"; exit 1; }
log "start; spite $(git rev-parse --short HEAD)"
# (e) versions and occupancy ceilings
{ nsys --version; ncu --version | tail -1; nvidia-smi --query-gpu=index,name,driver_version,clocks.sm,clocks.applications.graphics,clocks.mem,power.limit --format=csv; echo; cuobjdump -res-usage build/kernels/qwen/qwen3_5/nvidia/libkernel_qwen_qwen3_5_nvidia.so 2>&1 | grep -A2 -E 'gemv_batch|gemv_row'; } > $O/e_versions_resusage.txt 2>&1
log "(e) done: $(grep -c Function $O/e_versions_resusage.txt) gemv functions with res-usage"
# verify
timeout 900 python3 tools/verify/verify.py $VK > $O/verify.txt 2>&1; log "verify.py rc=$? $(grep -E 'PASSED|FAILED' $O/verify.txt | tail -1) OK=$(grep -c 'OK:' $O/verify.txt)"
LD_LIBRARY_PATH=$(dirname $CUDART) timeout 900 python3 tools/verify/verify_batch_cuda.py $VK $CUDART > $O/verify_batch.txt 2>&1; log "verify_batch_cuda rc=$? $(tail -1 $O/verify_batch.txt)"
# (f) real-text acceptance
timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --prompt "The history of the Roman Republic begins with the overthrow of the monarchy." --n-tokens 128 --n-runs 1 --mtp --draft-tokens 1 --json > $O/f_mtp_realtext.json 2> $O/f_mtp_realtext.err
log "(f) real-text --mtp K=1 rc=$? $(tr -d '\n' < $O/f_mtp_realtext.json | cut -c1-360)"
# refreshed rows
BB --n-prompt 512 --n-tokens 32 --n-runs 3 --json > $O/row_512.json 2> $O/row_512.err; log "row 512/32/3 rc=$? $(tr -d '\n' < $O/row_512.json | cut -c1-360)"
BB --json > $O/row_default.json 2> $O/row_default.err; log "row default rc=$? $(tr -d '\n' < $O/row_default.json | cut -c1-360)"
# (a) prompt-length scaling
for n in 8 32 128 512; do BB --n-prompt $n --n-tokens 4 --n-runs 1 --json > $O/a_n$n.json 2> $O/a_n$n.err; log "(a) n_prompt=$n rc=$? $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("ttft_ms", round(d["ttft_ms"],1), "prefill_tps", round(d["prefill_tps"],2))' $O/a_n$n.json 2>&1)"; done
# (b)+(d) nsys at both heads, with an nvidia-smi log during the caa2d72 512 run
nvidia-smi --query-gpu=timestamp,index,clocks.sm,clocks.mem,power.draw,power.limit,utilization.gpu,utilization.memory --format=csv -l 1 > $O/d_smi_512.log & SMI=$!
timeout 2400 nsys profile --force-overwrite=true --trace=cuda,osrt --cuda-memory-usage=true --stats=true -o $O/p100_prefill512_caa2d72 $B --model "$M" --card TESLA_P100 --device cuda --n-prompt 512 --n-tokens 4 --n-runs 1 > $O/b_nsys_caa2d72.txt 2>&1; log "(b) nsys caa2d72 512 rc=$?"
kill $SMI; nvidia-smi -q -d PERFORMANCE,ECC | head -80 > $O/d_smi_q.txt
timeout 2400 nsys profile --force-overwrite=true --trace=cuda,osrt --cuda-memory-usage=true --stats=true -o $O/p100_prefill512_f1cc494 $BF1/spite-bench --model "$M" --card TESLA_P100 --device cuda --kernels-dir $BF1/kernels --n-prompt 512 --n-tokens 4 --n-runs 1 > $O/b_nsys_f1cc494.txt 2>&1; log "(b) nsys f1cc494 512 rc=$?"
timeout 2400 nsys profile --force-overwrite=true --trace=cuda,osrt --cuda-memory-usage=true --stats=true -o $O/p100_prefill512_caa2d72_tok16 $B --model "$M" --card TESLA_P100 --device cuda --n-prompt 512 --n-tokens 16 --n-runs 1 > $O/b_nsys_caa2d72_tok16.txt 2>&1; log "(b) nsys caa2d72 512 tok16 rc=$?"
for r in p100_prefill512_caa2d72 p100_prefill512_f1cc494 p100_prefill512_caa2d72_tok16; do
  nsys stats --force-export=true --report cuda_gpu_kern_sum,cuda_gpu_kern_gb_sum,cuda_api_sum,cuda_gpu_mem_time_sum,cuda_gpu_mem_size_sum --format csv --output $O/stats_$r $O/$r.nsys-rep > $O/stats_$r.log 2>&1; log "stats $r rc=$?"; done
# (c) ncu counters (root required on this driver)
for k in gemv_batch_kernel gemv_row_kernel; do
  timeout 2400 sudo -n ncu --clock-control none --kernel-name regex:$k --launch-count 3 --launch-skip 60 --section SpeedOfLight \
    --metrics dram__bytes.sum,gpu__time_duration.sum,dram__throughput.avg.pct_of_peak_sustained_elapsed,sm__throughput.avg.pct_of_peak_sustained_elapsed,sm__warps_active.avg.pct_of_peak_sustained_active \
    $B --model "$M" --card TESLA_P100 --device cuda --n-prompt 512 --n-tokens 2 --n-runs 1 > $O/c_ncu_$k.txt 2>&1; log "(c) ncu $k rc=$?"
done
sudo -n chown -R $(id -u):$(id -g) $O 2>/dev/null
log TESTS_DONE
