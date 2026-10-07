#!/usr/bin/env bash
# R5-b on .73: llama.cpp MTP acceptance reference + spite --mtp K=2/3 on the real-text prompt; nsys re-profiles
# (CUDA trace only) for the two runs whose import failed; nvprof counters on the two GEMV kernels (ncu has no sm_60).
echo $$ > /tmp/apollo-busy.spite; trap 'rm -f /tmp/apollo-busy.spite; kill $LP 2>/dev/null' EXIT
cd ~/spite; O=~/spite-test/raw_r5; L=$O/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
M="/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf"; B=./target/release/spite-bench; BF1=~/spite-test/b_f1
LS=/mnt/HDD/buun-510cb-nohost/build_sm60/bin/llama-server
PR="The history of the Roman Republic begins with the overthrow of the monarchy."
pgrep -x llama-server >/dev/null && { log "ABORT: llama-server still running"; exit 1; }
log "R5-b start"
for k in 2 3; do timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --prompt "$PR" --n-tokens 128 --n-runs 1 --mtp --draft-tokens $k --json > $O/f_mtp_realtext_k$k.json 2> $O/f_mtp_realtext_k$k.err
  log "(f) real-text --mtp K=$k rc=$? $(tr -d '\n' < $O/f_mtp_realtext_k$k.json | cut -c1-260)"; done
# plain spite greedy text on the same prompt, for the token count and the comparison with llama.cpp
timeout 900 ./target/release/spite run -m "$M" --card TESLA_P100 --device cuda --ctx 8192 --temperature 0 --max-tokens 128 -p "$PR" > $O/f_spite_run_plain.out 2> $O/f_spite_run_plain.err; log "spite run plain rc=$? $(grep generate $O/f_spite_run_plain.err)"
# llama.cpp reference: MTP draft-max 1, same GGUF, -sm layer, greedy, no prompt cache
$LS -m "$M" -ngl 99 -sm layer -fa on -ctk f16 -ctv f16 -c 8192 -np 1 -fit off --spec-type draft-mtp --draft-max 1 --host 127.0.0.1 --port 8085 > $O/llama_mtp_server.log 2>&1 & LP=$!
for i in $(seq 1 300); do curl -sf -m 2 http://127.0.0.1:8085/health >/dev/null && break; kill -0 $LP || break; sleep 1; done
python3 - "$PR" > $O/llama_mtp_k1.json <<'PY'
import json, sys, urllib.request
req = {"prompt": sys.argv[1], "n_predict": 128, "temperature": 0, "top_k": 1, "cache_prompt": False, "ignore_eos": True}
print(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8085/completion", json.dumps(req).encode(), {"Content-Type": "application/json"}), timeout=900).read().decode())
PY
log "llama.cpp MTP K=1 rc=$? $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); t=d["timings"]; print("draft_n", t.get("draft_n"), "accepted", t.get("draft_n_accepted"), "acc", round(t.get("draft_n_accepted",0)/max(1,t.get("draft_n",0)),4), "predicted", t.get("predicted_n"), "tps", round(t.get("predicted_per_second",0),2))' $O/llama_mtp_k1.json 2>&1)"
kill $LP; wait $LP 2>/dev/null; LP=
# nsys re-profiles, CUDA trace only
for v in caa2d72 f1cc494; do BIN=$B; KD=""; [ $v = f1cc494 ] && { BIN=$BF1/spite-bench; KD="--kernels-dir $BF1/kernels"; }
  timeout 2400 nsys profile --force-overwrite=true --trace=cuda --stats=false -o $O/p100_prefill512_${v}_cudaonly $BIN --model "$M" --card TESLA_P100 --device cuda $KD --n-prompt 512 --n-tokens 4 --n-runs 1 > $O/b_nsys_${v}_cudaonly.txt 2>&1; log "(b) nsys $v cuda-only rc=$?"
  [ -f $O/p100_prefill512_${v}_cudaonly.qdstrm ] && /usr/lib/nsight-systems/host-linux-x64/QdstrmImporter -i $O/p100_prefill512_${v}_cudaonly.qdstrm > $O/import_${v}_cudaonly.log 2>&1; log "  import rc=$?"
  nsys stats --force-export=true --report cuda_gpu_kern_sum,cuda_gpu_kern_gb_sum,cuda_api_sum,cuda_gpu_mem_time_sum,cuda_gpu_mem_size_sum --format csv --output $O/stats_p100_prefill512_${v}_cudaonly $O/p100_prefill512_${v}_cudaonly.nsys-rep > $O/stats_${v}_cudaonly.log 2>&1; log "  stats rc=$?"
done
# nvprof counters (Pascal), short prompt so the replay finishes
for k in gemv_batch_kernel gemv_row_kernel; do
  timeout 2400 sudo -n nvprof --kernels "::${k}:1" --metrics dram_read_throughput,dram_read_transactions,gld_efficiency,achieved_occupancy,sm_efficiency,flop_count_sp,inst_executed,stall_memory_dependency,stall_exec_dependency \
    $B --model "$M" --card TESLA_P100 --device cuda --n-prompt 64 --n-tokens 2 --n-runs 1 > $O/c_nvprof_$k.txt 2>&1; log "(c) nvprof $k rc=$?"
done
sudo -n chown -R $(id -u):$(id -g) $O 2>/dev/null
log R5B_DONE
