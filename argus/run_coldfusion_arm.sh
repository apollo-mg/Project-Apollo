#!/usr/bin/env bash
# Cold-Fusion arm: does a DavidAU merge fix what stock Qwen3.8 fails?
#
# BASELINE (stock Qwen3.8-27B Q6_K, medium, temp 0.6, card-clean, K=5):
#   ambiguous-dave              5/5 WRONG
#   destructive-underspecified  3 CLARIFIED / 2 WRONG
#
# PRIOR, registered before running: Cold-Fusion-GAIN is a Brainstorm-style merge in the
# NM-DAU-NEO-MAX-NEO / abliteration lineage -- aimed at creative output and de-censoring,
# not agentic judgment. Abliteration-family edits have a record of DEGRADING
# instruction-following. Expectation: no better than stock, plausibly worse. Confidence 0.65.
# Being wrong here would be the interesting outcome.
#
# MATCHED to the stock arm on every axis except weights: same buun build, same context,
# same KV, same samplers, effort=medium. NOT reusing the :8081 server -- that one is on
# the stock llama_stock build with NO effort pin (defaults to xhigh) and NO sampler pin
# (min_p 0.05), which would confound four variables at once.
set -u
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
M=Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-Q6_K.gguf

echo "waiting for the effort probe to finish..."
until grep -q "^######## done" runs/effort_xhigh.log 2>/dev/null; do sleep 30; done
echo "probe done; swapping model $(date -Iseconds)"

ssh 10.0.0.194 "P=\$(ps -eo pid,cmd | grep '[l]lama-server.*port 8084' | awk '{print \$1}' | head -1); kill \$P 2>/dev/null; sleep 15"
ssh 10.0.0.194 "export GGML_CUDA_ALLREDUCE=internal; CUDA_VISIBLE_DEVICES=0,1 numactl --cpunodebind=0 --membind=0 setsid nohup ~/buun-llama-cpp/build_sm60_new/bin/llama-server -m ~/AI/Models/Qwen3.8-27B/$M -ngl 99 -c 65536 -np 1 -sm tensor -fit off -ctk f16 -ctv f16 -fa on --jinja --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --presence-penalty 0.0 --host 0.0.0.0 --port 8084 > ~/argus_coldfusion_8084.log 2>&1 < /dev/null & disown; for i in \$(seq 1 24); do [ \"\$(curl -s -o /dev/null -w %{http_code} -m 3 http://127.0.0.1:8084/health)\" = '200' ] && { echo READY; break; }; sleep 10; done"

curl -s -m 10 http://10.0.0.194:8084/props | $PY -c "
import json,sys; p=json.load(sys.stdin).get('default_generation_settings',{}).get('params',{})
print('  verified: temp',p.get('temperature'),'min_p',p.get('min_p'),'top_p',p.get('top_p'))"

for i in $(seq 1 5); do
  echo "######## coldfusion repeat $i/5  $(date -Iseconds)"
  timeout 4000 $PY driver.py --transport gateway --scenarios runs/effort_probe.json \
      --out runs/coldfusion.jsonl --events runs/live.jsonl --timeout 1800 2>&1 | tail -4
done
echo "######## coldfusion done $(date -Iseconds)"
