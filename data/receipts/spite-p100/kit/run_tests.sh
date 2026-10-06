#!/usr/bin/env bash
# PREREG_SPITE_PR23_73 GPU rows on .73 (T3-T8). Precondition: the daily-driver llama-server is stopped and the
# desktop wake proxy is down (it would relaunch llama-server into the test).
echo $$ > /tmp/apollo-busy.spite; trap 'rm -f /tmp/apollo-busy.spite; kill $LP 2>/dev/null' EXIT
cd ~/spite; O=~/spite-test/raw; mkdir -p $O; L=$O/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
M="/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf"; S=./target/release/spite; B=./target/release/spite-bench
LS=/mnt/HDD/buun-510cb-nohost/build_sm60/bin/llama-server
P=( $'Question: What is 17 multiplied by 23?\nAnswer:' $'Question: What is the capital of France?\nAnswer:'
    $'Question: Define photosynthesis in one sentence.\nAnswer:' 'The old man walked to the harbor and' )
pgrep -x llama-server >/dev/null && { log "ABORT: llama-server still running"; exit 1; }
nvidia-smi --query-gpu=index,name,clocks.sm,clocks.applications.graphics,power.limit,memory.used --format=csv > $O/gpu_state_start.csv
log "start; spite $(git rev-parse --short HEAD)"
# T3/T4: A = default placement, B = stage order reversed, C = default again
for i in 0 1 2 3; do
  for cfg in A B C; do
    X=""; [ $cfg = B ] && X="--gpus 1,0"
    f=$O/t3_p$((i+1))_$cfg
    timeout 900 $S run -m "$M" --card TESLA_P100 --device cuda --ctx 8192 --temperature 0 --max-tokens 128 $X -p "${P[$i]}" > $f.out 2> $f.err
    rc=$?; log "T3/T4 p$((i+1)) $cfg rc=$rc stage-lines=$(cat $f.out $f.err | grep -c 'stage *:') out-bytes=$(wc -c < $f.out)"
    [ $rc != 0 ] && log "  err: $(tail -3 $f.err | tr '\n' ' ' | cut -c1-300)"
  done
done
for i in 1 2 3 4; do
  cmp -s $O/t3_p${i}_A.out $O/t3_p${i}_B.out && ab=same || ab=DIFF; cmp -s $O/t3_p${i}_A.out $O/t3_p${i}_C.out && ac=same || ac=DIFF
  log "T4 p$i: A vs B(reversed) $ab, A vs C(repeat) $ac"
done
# T8: MTP on, prompt 4
timeout 900 $S run -m "$M" --card TESLA_P100 --device cuda --ctx 8192 --temperature 0 --max-tokens 128 --mtp -p "${P[3]}" > $O/t8_mtp.out 2> $O/t8_mtp.err
log "T8 run --mtp rc=$? $(cmp -s $O/t8_mtp.out $O/t3_p4_A.out && echo same-as-A || echo differs-from-A)"
# T7: spite-bench defaults, then with MTP
timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --json > $O/t7_bench.json 2> $O/t7_bench.err; log "T7 spite-bench rc=$? $(tr -d '\n' < $O/t7_bench.json | cut -c1-400)"
timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --mtp --json > $O/t8_bench_mtp.json 2> $O/t8_bench_mtp.err; log "T8 spite-bench --mtp rc=$? $(tr -d '\n' < $O/t8_bench_mtp.json | cut -c1-400)"
nvidia-smi --query-gpu=index,clocks.sm,memory.used --format=csv,noheader > $O/gpu_state_after_spite.csv
# llama.cpp reference, pipeline-matched
$LS -m "$M" -ngl 99 -sm layer -fa on -ctk f16 -ctv f16 -c 8192 -np 1 -fit off --host 127.0.0.1 --port 8085 > $O/llama_server.log 2>&1 & LP=$!
for i in $(seq 1 300); do curl -sf -m 2 http://127.0.0.1:8085/health >/dev/null && break; kill -0 $LP || break; sleep 1; done
log "llama.cpp up: $(curl -s -m 2 http://127.0.0.1:8085/health); VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' ' ')"
for i in 0 1 2 3; do
  python3 - "${P[$i]}" > $O/t5_llama_p$((i+1)).json <<'PY'
import json, sys, urllib.request
req = {"prompt": sys.argv[1], "n_predict": 128, "temperature": 0, "top_k": 1, "cache_prompt": False, "return_tokens": True}
r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8085/completion", json.dumps(req).encode(), {"Content-Type": "application/json"}), timeout=600)
print(r.read().decode())
PY
  log "T5 llama p$((i+1)) rc=$?"
done
python3 - > $O/t7_llama.json <<'PY'
import json, urllib.request, statistics
def go(n):
    req = {"prompt": "Benchmark prompt for throughput measurement.", "n_predict": n, "temperature": 0, "top_k": 1, "cache_prompt": False, "ignore_eos": True}
    return json.loads(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8085/completion", json.dumps(req).encode(), {"Content-Type": "application/json"}), timeout=1200).read())["timings"]
go(16)
t = [go(512) for _ in range(3)]
print(json.dumps({"runs": t, "median_decode_tps": statistics.median(x["predicted_per_second"] for x in t), "median_prompt_tps": statistics.median(x["prompt_per_second"] for x in t)}))
PY
log "T7 llama.cpp -sm layer rc=$? $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("decode", round(d["median_decode_tps"],2), "prompt", round(d["median_prompt_tps"],1), [round(x["predicted_per_second"],2) for x in d["runs"]], "n", [x["predicted_n"] for x in d["runs"]])' $O/t7_llama.json)"
kill $LP; wait $LP 2>/dev/null
nvidia-smi --query-gpu=index,clocks.sm,clocks.applications.graphics --format=csv,noheader > $O/gpu_state_end.csv
log TESTS_DONE
