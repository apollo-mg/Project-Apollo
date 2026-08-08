#!/usr/bin/env bash
# Finding 5 resolution: is the Gemma cap-death/silent-closure discrepancy a SERVING-PATH
# artifact? This drives Gemma through the PANEL's path -- lm-eval-harness, --apply_chat_template,
# MTP on, max_gen_toks 4096 -- instead of this leg's direct POST to /v1/chat/completions.
#
# Discriminator: IFEval doc_ids 0, 7 and 9 are in both this run (--limit 10) and our cells.
# All three CAP-DIED on the direct path (finish=length, zero answer). If the harness path
# produces answers for them, explanation (2) "serving path" is confirmed and the panel's
# "zero budget-cap hits" stands. If they truncate here too, (2) is ruled out.
set -u
R=/mnt/TG_2TB/Projects/Apollo/data/receipts/battle16gb/reasoning_budget_smoke
P=/mnt/TG_2TB/Projects/Apollo
SP=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
OUT="$R/f5_harness"
mkdir -p "$OUT"

pkill -x llama-server 2>/dev/null; sleep 4
# Panel serving config for Gemma: MTP on, -c 16384, port 8094 (Lab_Spec_Battle16GB.md sec 3).
"$P/engines/llama_cpp_turboquant/build_rocm/bin/llama-server" \
  -m "/mnt/TG_2TB/AI/Models/Gemma 4/12B/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf" \
  -c 16384 -ngl 99 -fa on -ctk f16 -ctv f16 --jinja \
  --reasoning-format deepseek \
  --spec-type draft-mtp --spec-draft-model "$SP/mtp-gemma.gguf" --spec-draft-n-max 3 \
  --host 127.0.0.1 --port 8094 > "$OUT/server.log" 2>&1 &

for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:8094/health >/dev/null 2>&1 && break
  sleep 3
done
curl -sf http://127.0.0.1:8094/health >/dev/null 2>&1 || {
  echo "FATAL: server never became ready"; tail -20 "$OUT/server.log"; exit 1; }
echo "=== server up (panel config: MTP on, c=16384) ==="

"$P/venv_cachyos/bin/python3" -m lm_eval \
  --model local-chat-completions \
  --model_args "base_url=http://127.0.0.1:8094/v1/chat/completions,model=gemma,num_concurrent=1,max_retries=1,tokenized_requests=False" \
  --tasks ifeval \
  --apply_chat_template \
  --limit 10 \
  --gen_kwargs "max_gen_toks=4096,temperature=0" \
  --output_path "$OUT" \
  --log_samples \
  --seed 42 2>&1 | tail -30
rc=$?

pkill -x llama-server 2>/dev/null; sleep 3
head -300 "$OUT/server.log" > "$OUT/server.log.trim" && mv "$OUT/server.log.trim" "$OUT/server.log"
echo "=== harness rc=$rc ==="
find "$OUT" -name '*.jsonl' | head
