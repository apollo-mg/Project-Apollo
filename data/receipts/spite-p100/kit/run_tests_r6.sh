#!/usr/bin/env bash
# PREREG_SPITE_PR23_73 Addendum R6 on .73: round 6 (2a7d5ac) + row tiling (69676bc), one pass.
# Precondition: daily-driver server and wake proxy down; ~/spite at 69676bc with b_6e7/ and b_2a7/ saved.
echo $$ > /tmp/apollo-busy.spite; trap 'rm -f /tmp/apollo-busy.spite; kill $LP 2>/dev/null' EXIT
cd ~/spite; O=~/spite-test/raw_r6; mkdir -p $O; L=$O/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
M="/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf"; M2=~/spite-test/models/Qwen3.5-2B-Q6_K.gguf
S=./target/release/spite; B=./target/release/spite-bench; T=~/spite-test
CUDART=/usr/lib/x86_64-linux-gnu/libcudart.so.12; VK=kernels/qwen/qwen3_5/nvidia/libkernel_qwen_qwen3_5_nvidia.so
LS=/mnt/HDD/buun-510cb-nohost/build_sm60/bin/llama-server
PR="The history of the Roman Republic begins with the overthrow of the monarchy."
P=( $'Question: What is 17 multiplied by 23?\nAnswer:' $'Question: What is the capital of France?\nAnswer:'
    $'Question: Define photosynthesis in one sentence.\nAnswer:' 'The old man walked to the harbor and' )
gpu() { nvidia-smi --query-gpu=timestamp,index,clocks.sm,clocks.applications.graphics,power.limit,memory.used --format=csv,noheader >> $O/gpu_state.csv; }
j() { tr -d '\n' < "$1" | cut -c1-420; }
gen() { python3 -c 'import sys,re; t=open(sys.argv[1],encoding="utf-8").read(); m=re.search(r"stage +: GPU \d+ .*layers \d+\.\.64[^\n]*\n",t); print(repr(t[m.end()+1:] if m else "NO-STAGE-LINE:"+t[-200:]))' "$1"; }
pgrep -x llama-server >/dev/null && { log "ABORT: llama-server still running"; exit 1; }
gpu; log "start; spite $(git rev-parse --short HEAD)"
cp $T/resusage_2a7d5ac.txt $T/resusage_69676bc.txt $O/ 2>/dev/null
# verify at 69676bc
timeout 900 python3 tools/verify/verify.py $VK > $O/verify.txt 2>&1; log "verify.py rc=$? $(grep -E 'PASSED|FAILED' $O/verify.txt | tail -1) OK=$(grep -c 'OK:' $O/verify.txt) SKIP=$(grep -c SKIP $O/verify.txt)"
LD_LIBRARY_PATH=$(dirname $CUDART) timeout 900 python3 tools/verify/verify_batch_cuda.py $VK $CUDART > $O/verify_batch.txt 2>&1; log "verify_batch_cuda rc=$? $(tail -1 $O/verify_batch.txt)"
# 27B prefill rows at the three binaries
for v in 6e7 2a7 head; do
  if [ $v = head ]; then BIN=$B; KD=""; else BIN=$T/b_$v/spite-bench; KD="--kernels-dir $T/b_$v/kernels"; fi
  gpu; timeout 2400 $BIN --model "$M" --card TESLA_P100 --device cuda $KD --n-prompt 512 --n-tokens 32 --n-runs 3 --json > $O/row512_$v.json 2> $O/row512_$v.err
  log "27B row 512/32/3 $v rc=$? $(j $O/row512_$v.json)"
done
gpu; timeout 2400 $B --model "$M" --card TESLA_P100 --device cuda --json > $O/row_default.json 2> $O/row_default.err; log "27B row default rc=$? $(j $O/row_default.json)"
# 27B MTP on the Roman Republic prompt, K=1..3, plus plain on the same prompt
timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --prompt "$PR" --n-tokens 128 --n-runs 1 --json > $O/mtp27_plain.json 2> $O/mtp27_plain.err; log "27B Roman plain rc=$? $(j $O/mtp27_plain.json)"
for k in 1 2 3; do timeout 1800 $B --model "$M" --card TESLA_P100 --device cuda --prompt "$PR" --n-tokens 128 --n-runs 1 --mtp --draft-tokens $k --json > $O/mtp27_k$k.json 2> $O/mtp27_k$k.err
  log "27B Roman --mtp K=$k rc=$? $(j $O/mtp27_k$k.json) $(grep -i -E 'error|TV' $O/mtp27_k$k.err | tail -2 | tr '\n' ' ' | cut -c1-200)"; done
# greedy text: 4 prompts plain vs R4, and --mtp vs plain on the Roman prompt
for i in 0 1 2 3; do f=$O/t3_p$((i+1))
  timeout 900 $S run -m "$M" --card TESLA_P100 --device cuda --ctx 8192 --temperature 0 --max-tokens 128 -p "${P[$i]}" > $f.out 2> $f.err; rc=$?
  gen $f.out > $f.gen; cmp -s $f.gen $T/raw_r4/t3_p$((i+1))_A.gen && s=same-as-R4 || s=DIFFERS-FROM-R4; log "T3 p$((i+1)) rc=$rc $s $(grep generate $f.err)"; done
for x in plain mtp; do X=""; [ $x = mtp ] && X="--mtp"; f=$O/roman_run_$x
  timeout 900 $S run -m "$M" --card TESLA_P100 --device cuda --ctx 8192 --temperature 0 --max-tokens 128 $X -p "$PR" > $f.out 2> $f.err; log "Roman spite run $x rc=$? $(grep generate $f.err)"; gen $f.out > $f.gen; done
cmp -s $O/roman_run_plain.gen $O/roman_run_mtp.gen && log "Roman run: --mtp text same as plain" || log "Roman run: --mtp TEXT DIFFERS"
# 2B: CPU gate row, CUDA rows, unsplit MTP
gpu; timeout 2400 $B --model $M2 --device cpu --n-prompt 16 --n-tokens 8 --n-runs 1 --json > $O/q2b_cpu_gate.json 2> $O/q2b_cpu_gate.err; log "2B CPU gate rc=$? $(j $O/q2b_cpu_gate.json) $(tail -2 $O/q2b_cpu_gate.err | tr '\n' ' ' | cut -c1-200)"
timeout 1200 $B --model $M2 --card TESLA_P100 --device cuda --n-prompt 16 --n-tokens 8 --n-runs 1 --json > $O/q2b_cuda_gate.json 2> $O/q2b_cuda_gate.err; log "2B CUDA gate-shape rc=$? $(j $O/q2b_cuda_gate.json)"
timeout 1200 $B --model $M2 --card TESLA_P100 --device cuda --json > $O/q2b_cuda_default.json 2> $O/q2b_cuda_default.err; log "2B CUDA default rc=$? $(j $O/q2b_cuda_default.json) $(grep -i stage $O/q2b_cuda_default.err | tr '\n' ' ')"
timeout 1200 $B --model $M2 --card TESLA_P100 --device cuda --prompt "$PR" --n-tokens 128 --n-runs 1 --json > $O/mtp2b_plain.json 2> $O/mtp2b_plain.err; log "2B Roman plain rc=$? $(j $O/mtp2b_plain.json)"
for k in 1 2 3; do timeout 1200 $B --model $M2 --card TESLA_P100 --device cuda --prompt "$PR" --n-tokens 128 --n-runs 1 --mtp --draft-tokens $k --json > $O/mtp2b_k$k.json 2> $O/mtp2b_k$k.err
  log "2B Roman --mtp K=$k rc=$? $(j $O/mtp2b_k$k.json) $(grep -i stage $O/mtp2b_k$k.err | tr '\n' ' ')"; done
# llama.cpp reference on the 2B, one GPU, MTP K=1
CUDA_VISIBLE_DEVICES=0 $LS -m $M2 -ngl 99 -fa on -ctk f16 -ctv f16 -c 8192 -np 1 -fit off --spec-type draft-mtp --draft-max 1 --host 127.0.0.1 --port 8085 > $O/llama2b_mtp_server.log 2>&1 & LP=$!
for i in $(seq 1 300); do curl -sf -m 2 http://127.0.0.1:8085/health >/dev/null && break; kill -0 $LP || break; sleep 1; done
python3 - "$PR" > $O/llama2b_mtp_k1.json <<'PY'
import json, sys, urllib.request
req = {"prompt": sys.argv[1], "n_predict": 128, "temperature": 0, "top_k": 1, "cache_prompt": False, "ignore_eos": True}
print(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8085/completion", json.dumps(req).encode(), {"Content-Type": "application/json"}), timeout=900).read().decode())
PY
log "llama.cpp 2B MTP K=1 rc=$? $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); t=d["timings"]; print("draft_n", t.get("draft_n"), "accepted", t.get("draft_n_accepted"), "acc", round(t.get("draft_n_accepted",0)/max(1,t.get("draft_n",0)),4), "predicted", t.get("predicted_n"), "tps", round(t.get("predicted_per_second",0),2))' $O/llama2b_mtp_k1.json 2>&1)"
kill $LP; wait $LP 2>/dev/null; LP=
gpu; log TESTS_DONE
