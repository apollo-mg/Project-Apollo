#!/usr/bin/env bash
# Settle the Bonferroni question: stock and Cold-Fusion to n=24 on destructive-underspecified.
# At n=12 the gap is 25% vs 83%, p=0.012 nominal -- but 6 comparisons give alpha=0.0083, so it
# does NOT survive correction. Only this scenario is extended; ambiguous-dave is 1/12 on all
# four arms (a floor) and more runs there buy nothing.
set -u
A=/mnt/TG_2TB/Projects/Apollo/argus
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
M27=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
MCF=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-Q6_K.gguf
cd "$A"
serve () {
  ssh 10.0.0.194 "P=\$(ss -ltnp 2>/dev/null | grep -oE ':8086.*pid=[0-9]+' | grep -oE '[0-9]+$' | head -1); [ -n \"\$P\" ] && kill \$P; sleep 12; export GGML_CUDA_ALLREDUCE=internal; CUDA_VISIBLE_DEVICES=2,3 numactl --cpunodebind=1 --membind=1 setsid nohup ~/buun-llama-cpp/build_sm60_new/bin/llama-server -m $1 -ngl 99 -c 65536 -np 1 -sm tensor -fit off -ctk f16 -ctv f16 -fa on --jinja --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --presence-penalty 0.0 --host 0.0.0.0 --port 8086 > ~/n24_8086.log 2>&1 < /dev/null & disown; for i in \$(seq 1 24); do [ \"\$(curl -s -o /dev/null -w %{http_code} -m 3 http://127.0.0.1:8086/health)\" = '200' ] && { echo READY; break; }; sleep 10; done"
}
run () {
  for i in $(seq 1 12); do
    echo "######## $1 ext $i/12  $(date -Iseconds)"
    timeout 4000 $PY driver.py --transport gateway --base http://127.0.0.1:8645 \
      --fake-root $A/fixtures/ref/fake-google --scenarios runs/destr_only.json \
      --out runs/$1_n24.jsonl --events runs/live_ref.jsonl --timeout 900 2>&1 | tail -3
  done
}
echo "=== stock +12 ==="; serve "$M27"; run stock
echo "=== cold-fusion +12 ==="; serve "$MCF"; run coldfusion
echo "### n24 extension done $(date -Iseconds)"
