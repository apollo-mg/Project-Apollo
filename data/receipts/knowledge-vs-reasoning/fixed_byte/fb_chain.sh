#!/usr/bin/env bash
# Fixed-byte allocation arms — PREREG_FIXED_BYTE.md (57a82de).
# ~13.2 GB each; prune ratio traded against quantization depth.
# FB-REAP50 (Q6_K, 32 experts) is NOT re-run: the dose-response leg measured that exact file under
# these exact settings (--max-tokens 160, forced GLM template), so its jsonl is reused verbatim.
set -u
D=/home/mark/reap_ladder
K=/home/mark/ikp_glm
BIN=/home/mark/tom_default/build/bin/llama-server
TMPL=/home/mark/glm_chat_template.jinja
OUT=/home/mark/fb_out
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
    echo "FATAL: $label did NOT load the GLM chat template (G-1b)"; exit 1
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

run_arm FBBASE   "$D/FB-BASE-Q3_K_S.gguf"      64
run_arm FBREAP09 "$D/FB-REAP09-Q3_K_M.gguf"    58
run_arm FBREAP19 "$D/FB-REAP19-Q3_K_L.gguf"    52
run_arm FBREAP39 "$D/FB-REAP39-Q5_K_S.gguf"    39
echo "===== FIXED-BYTE RUN DONE ====="
wc -l "$OUT"/ikp_*.jsonl
