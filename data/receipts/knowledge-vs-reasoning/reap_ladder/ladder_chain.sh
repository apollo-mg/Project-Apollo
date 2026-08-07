#!/usr/bin/env bash
# REAP dose-response ladder — 5 arms, prune ratio the only variable.
# Pre-registered: data/receipts/knowledge-vs-reasoning/PREREG_REAP_DOSE_RESPONSE.md (6184f08),
# AMENDMENT 1 (a2831d0) after run 1 was voided by a 93pp G-5 trip.
#
# Gates asserted from the runtime's own output BEFORE any probe is sent:
#   G-1  n_expert matches the arm (64/58/52/39/32)
#   G-1a expert_gating_func = sigmoid            (checked independently by ikp_run.py)
#   G-1b the GLM chat template actually loaded   <- NEW. The four Akicou GGUFs carry no
#        tokenizer.chat_template KV, so --jinja silently falls back to ChatML, which GLM was
#        never trained on. Discriminator verified against run 1: the ChatML fallback does NOT
#        emit "chat template supports preserving reasoning"; the real GLM template does.
set -u
D=/home/mark/reap_ladder
K=/home/mark/ikp_glm
BIN=/home/mark/tom_default/build/bin/llama-server
TMPL=/home/mark/glm_chat_template.jinja
OUT=/home/mark/ladder_out
PORT=8091
mkdir -p "$OUT"
[ -s "$TMPL" ] || { echo "FATAL: chat template $TMPL missing"; exit 1; }

run_arm() {
  local label=$1 model=$2 want=$3
  echo "########## ARM $label  (expect n_expert=$want)  $(date +%H:%M:%S)"
  [ -s "$model" ] || { echo "FATAL: missing $model"; exit 1; }
  pkill -x llama-server 2>/dev/null; sleep 5
  "$BIN" -m "$model" -c 4096 -ngl 99 -sm layer -np 1 --jinja -v \
         --chat-template-file "$TMPL" \
         --host 127.0.0.1 --port $PORT > "$OUT/${label}_load.log" 2>&1 &
  for i in $(seq 1 240); do
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
    sleep 5
  done
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 || {
    echo "FATAL: $label server never became ready"; tail -20 "$OUT/${label}_load.log"; exit 1; }

  got=$(grep -aE "print_info: n_expert[[:space:]]+=" "$OUT/${label}_load.log" \
        | head -1 | sed 's/.*=[[:space:]]*//' | tr -d '[:space:]')
  if [ "$got" != "$want" ]; then
    echo "FATAL: $label reports n_expert=$got, expected $want"; exit 1
  fi
  echo "=== $label G-1 confirmed n_expert=$got"

  if ! grep -qa "chat template supports preserving reasoning" "$OUT/${label}_load.log"; then
    echo "FATAL: $label did NOT load the GLM chat template (G-1b) — ChatML fallback suspected"
    exit 1
  fi
  echo "=== $label G-1b chat template OK"

  python3 "$K/ikp_run.py" --endpoint "http://127.0.0.1:$PORT" --label "$label" \
      --probes "$K/ikp_probes.json" --out "$OUT/ikp_${label}.jsonl" \
      --tiers T1,T2,T3,T4 --exclude-source researcher --no-think --max-tokens 160 \
      --assert-load-log "$OUT/${label}_load.log" --require-gating sigmoid
  rc=$?
  if [ "$rc" -ne 0 ]; then echo "FATAL: $label ikp run failed (rc=$rc)"; exit 1; fi

  pkill -x llama-server 2>/dev/null; sleep 5
  echo "=== $label DONE $(date +%H:%M:%S)"
}

run_arm BASE   "$D/GLM-4.7-Flash-BASE-Q6_K.gguf"     64
run_arm REAP09 "$D/GLM-4.7-Flash-REAP-09-Q6_K.gguf"  58
run_arm REAP19 "$D/GLM-4.7-Flash-REAP-19-Q6_K.gguf"  52
run_arm REAP39 "$D/GLM-4.7-Flash-REAP-39-Q6_K.gguf"  39
run_arm REAP50 "$D/GLM-4.7-Flash-REAP-50-Q6_K.gguf"  32
echo "===== LADDER RUN DONE ====="
wc -l "$OUT"/ikp_*.jsonl
