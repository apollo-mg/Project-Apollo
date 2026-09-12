#!/bin/bash
# einstein_chain.sh -- PREREG_EINSTEIN_TERMINATION.md (+ Amendments 1-2), primary then secondary.
#
#   PRIMARY    base Qwen3.8-27B UD-IQ4_XS, -c 12288 (Amendment 1)
#   SECONDARY  DavidAU TURBO-735-882 -MTP- IQ2_M, -c 16384 as originally registered
#
# Each leg gets a FRESH llama-server (server uptime is a variable). A leg refuses to start unless the
# live server reports the expected model, context and q8_0 KV (kv_bpv 8.5) -- buun's fork arms VBR if
# -ctk/-ctv are ever dropped. run_einstein.py skips cells already recorded, so re-running this script
# after a kill resumes rather than repeats.
set -u
cd /mnt/TG_2TB/Projects/Apollo/data/receipts/viability || exit 1
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
BIN=/mnt/TG_2TB/Projects/buun-aad85/build_rocm/bin/llama-server
TPL=/mnt/TG_2TB/Projects/Apollo/templates/twin-turbo/twin_turbo_template_fixed.jinja
M1=/mnt/TG_2TB/AI/Models/unsloth-v3/Qwen3.8-27B-UD-IQ4_XS.gguf
M2=/mnt/TG_2TB/AI/Models/davidau_turbo/Qwen3.8-27B-TurboFCFusion-735-882-Here-Uncen-NEO-CODER-MAX-MTP-IQ2_M.gguf
H=http://127.0.0.1:8097

log () { echo "$(date '+%F %T') $*" | tee -a einstein_chain.log; }

stop_server () {
  local P; P=$(pgrep -x llama-server)
  log "stopping llama-server pid(s): ${P:-none}"
  [ -n "$P" ] && kill $P
  for _ in $(seq 1 15); do pgrep -x llama-server >/dev/null || return 0; sleep 1; done
  log "still up after 15s, SIGKILL"; kill -9 $(pgrep -x llama-server) 2>/dev/null; sleep 2
}
start_server () {   # start_server <model> <n_ctx> <logfile>
  nohup setsid $BIN -m "$1" --chat-template-file "$TPL" -ngl 99 -c "$2" -np 1 -fa on --kv-unified \
    -ctk q8_0 -ctv q8_0 --jinja --host 127.0.0.1 --port 8097 > "$3" 2>&1 < /dev/null &
}
# Readiness is a real completion. /health returns 200 before the model is loaded.
ready () {
  for _ in $(seq 1 60); do
    curl -s -m 10 $H/v1/chat/completions -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"Say READY"}],"max_tokens":8}' 2>/dev/null \
      | grep -q '"content"' && return 0
    sleep 10
  done
  return 1
}
live () {
  curl -s -m 8 $H/slots 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin)[0]; print(d.get('n_ctx'), d.get('kv_bpv'))" 2>/dev/null
}
modelpath () {
  curl -s -m 8 $H/props 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('model_path',''))" 2>/dev/null
}
expect () {   # expect <model-filename-substring> <n_ctx>
  local mp cfg
  mp=$(modelpath); cfg=$(live)
  log "live server: model=$(basename "$mp") ctx/kv_bpv=$cfg"
  [[ "$mp" == *"$1"* ]] || { log "ABORT: expected a model containing '$1'"; return 1; }
  [ "$cfg" = "$2 8.5" ]  || { log "ABORT: expected '$2 8.5' (ctx, q8_0 kv_bpv), got '$cfg'"; return 1; }
}

mkdir -p einstein_iq4 einstein_iq2

log "=== PRIMARY: base Qwen3.8-27B UD-IQ4_XS (fresh server) ==="
stop_server
start_server "$M1" 12288 einstein_iq4/server.log
ready || { log "ABORT: IQ4_XS server never answered a real completion"; exit 1; }
expect "UD-IQ4_XS" 12288 || exit 1
EIN_MODEL="unsloth/Qwen3.8-27B-GGUF:Qwen3.8-27B-UD-IQ4_XS.gguf sha256=40fac4050e940397dbf13087afd50f4734a11805bf9d65ef8ddd7483470e6199" \
  $PY -u run_einstein.py --out einstein_iq4 --all 2>&1 | tee -a einstein_chain.log
log "primary rows: $(cat einstein_iq4/arm*_rep*.jsonl 2>/dev/null | wc -l) / 36"

log "=== SECONDARY: DavidAU TURBO-735-882 -MTP- IQ2_M (fresh server) ==="
stop_server
start_server "$M2" 16384 einstein_iq2/server.log
ready || { log "ABORT: IQ2_M server never answered a real completion"; exit 1; }
expect "MTP-IQ2_M" 16384 || exit 1
EIN_MODEL="DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NEO-CODER-MAX-MTP-GGUF:Qwen3.8-27B-TurboFCFusion-735-882-Here-Uncen-NEO-CODER-MAX-MTP-IQ2_M.gguf sha256=ee4fc4950338cc95e804bff5d5c51f0a55ef7b196f9dd6fbaddf62183d189dda" \
  $PY -u run_einstein.py --out einstein_iq2 --all 2>&1 | tee -a einstein_chain.log
log "secondary rows: $(cat einstein_iq2/arm*_rep*.jsonl 2>/dev/null | wc -l) / 36"
log "=== CHAIN COMPLETE ==="
