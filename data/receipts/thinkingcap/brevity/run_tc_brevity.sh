#!/usr/bin/env bash
# Brevity A/B: stock Qwen3.6-27B Q8_0 vs ThinkingCap Q8_0-MTP, thinking ON, matched quant.
# 40 prompts x 2 seeds per side, deployment sampling, think/answer tokens counted separately.
set -u
SRV=/home/mark/llama_stock/build_puzzle/bin/llama-server
OUT=/home/mark/quant_ladder
STOCK="/home/mark/AI/Models/Qwen 3.6/27B/Qwen3.6-27B-Q8_0.gguf"
TC="/home/mark/AI/Models/Qwen 3.6/27B-ThinkingCap/ThinkingCap-Qwen3.6-27B-Q8_0-MTP.gguf"

# don't fight the tensor-hash job for disk
while [ ! -f "$OUT/tc_tensor.DONE" ]; do sleep 30; done

run_side () {
  local name="$1" model="$2"
  echo "$(date '+%F %T') starting server: $name"
  "$SRV" -m "$model" \
    -c 32768 -np 4 -ngl 99 -sm layer -ts 1,1,1,1 -fit off -fa off \
    --reasoning on --reasoning-format deepseek --jinja \
    --host 127.0.0.1 --port 8090 \
    > "$OUT/brevity_server_${name}.log" 2>&1 &
  local pid=$!
  for i in $(seq 1 120); do
    curl -s -m 3 http://127.0.0.1:8090/health 2>/dev/null | grep -q '"status":"ok"' && break
    kill -0 $pid 2>/dev/null || { echo "SERVER DIED ($name)"; return 2; }
    sleep 10
  done
  curl -s -m 3 http://127.0.0.1:8090/health | grep -q '"status":"ok"' || { echo "SERVER NEVER READY ($name)"; kill $pid; return 3; }
  echo "$(date '+%F %T') generating: $name"
  ~/venv/bin/python3 "$OUT/gen_brevity.py" "$OUT/brevity_${name}.jsonl" 2>&1 | tee "$OUT/brevity_gen_${name}.log"
  local rc=${PIPESTATUS[0]}
  echo "$(date '+%F %T') gen rc=$rc — stopping $name pid $pid"
  kill $pid; sleep 10; kill -9 $pid 2>/dev/null
  sleep 5
  return $rc
}

run_side stock "$STOCK" || { echo "STOCK SIDE FAILED"; touch "$OUT/tc_brevity.DONE"; exit 1; }
run_side tc "$TC"       || { echo "TC SIDE FAILED";    touch "$OUT/tc_brevity.DONE"; exit 1; }

echo "$(date '+%F %T') analyzing"
~/venv/bin/python3 "$OUT/analyze_brevity.py" "$OUT/brevity_stock.jsonl" "$OUT/brevity_tc.jsonl" \
  > "$OUT/brevity_analysis.txt" 2>&1
cat "$OUT/brevity_analysis.txt"
touch "$OUT/tc_brevity.DONE"
echo "$(date '+%F %T') BREVITY COMPLETE"
