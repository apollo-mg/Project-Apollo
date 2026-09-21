#!/usr/bin/env bash
# Carnice-V3 arm — the agentic fine-tune of our exact base model.
#
# Carnice-V3 = Qwen3.8-27B + rank-64 rsLoRA merged into language modules (vision/MTP frozen),
# trained on 8 private trajectories across 6 agent-task families for Hermes tool-use accuracy.
# 24 SFT windows, 162K tokens. Author's own card: verifier signals improved, "long-horizon
# completion and task-level tool contracts regressed", "did not pass its formal behavioral
# quality gate", and explicitly "not recommended for unattended, destructive, high-stakes
# agents without independent evaluation".
#
# CORPUS CAVEAT, stated up front: all six of our scenarios are SHORT-horizon (2-4 tool calls).
# The author says short-horizon verifier signals are the half that IMPROVED. So a good result
# here measures the half they already said got better, on a corpus with zero long-horizon
# items. That is a limitation of our corpus, not a win for the model.
#
# Matched to the stock arm on every axis except weights: same buun build, Q6_K (NOT their
# recommended Q5_K_M -- quant must not confound), same context, same KV, effort=medium,
# card-clean samplers at temp 0.6.
set -u
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
GG=/mnt/TG_2TB/AI/Models/carnice/Carnice-V3-Q6_K.gguf

echo "waiting for download..."
until [ -f "$GG" ] && ! find /mnt/TG_2TB/AI/Models/carnice -name "*.incomplete" | grep -q .; do sleep 30; done
echo "download complete: $(du -h $GG | cut -f1)  $(date -Iseconds)"

echo "waiting for the Cold-Fusion extension to finish..."
until grep -q "^######## done" runs/coldfusion_ext.log 2>/dev/null; do sleep 30; done

echo "shipping model to .194 $(date -Iseconds)"
rsync -a --info=progress2 "$GG" 10.0.0.194:~/AI/Models/ 2>&1 | tail -1

ssh 10.0.0.194 "P=\$(ps -eo pid,cmd | grep '[l]lama-server.*port 8084' | awk '{print \$1}' | head -1); kill \$P 2>/dev/null; sleep 15"
ssh 10.0.0.194 "export GGML_CUDA_ALLREDUCE=internal; CUDA_VISIBLE_DEVICES=0,1 numactl --cpunodebind=0 --membind=0 setsid nohup ~/buun-llama-cpp/build_sm60_new/bin/llama-server -m ~/AI/Models/Carnice-V3-Q6_K.gguf -ngl 99 -c 65536 -np 1 -sm tensor -fit off -ctk f16 -ctv f16 -fa on --jinja --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --presence-penalty 0.0 --host 0.0.0.0 --port 8084 > ~/argus_carnice_8084.log 2>&1 < /dev/null & disown; for i in \$(seq 1 30); do [ \"\$(curl -s -o /dev/null -w %{http_code} -m 3 http://127.0.0.1:8084/health)\" = '200' ] && { echo READY; break; }; sleep 10; done"

curl -s -m 10 http://10.0.0.194:8084/props | $PY -c "
import json,sys; p=json.load(sys.stdin).get('default_generation_settings',{}).get('params',{})
print('  verified samplers: temp',p.get('temperature'),'min_p',p.get('min_p'),'top_p',p.get('top_p'))"

for i in $(seq 1 12); do
  echo "######## carnice repeat $i/12  $(date -Iseconds)"
  timeout 4000 $PY driver.py --transport gateway --scenarios runs/effort_probe.json \
      --out runs/carnice.jsonl --events runs/live.jsonl --timeout 1800 2>&1 | tail -4
done
echo "######## carnice done $(date -Iseconds)"
