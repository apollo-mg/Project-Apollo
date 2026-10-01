#!/usr/bin/env bash
# PREREG_CODER_PRUNE.md orchestrator (desktop). Per arm: fresh verified server on .194 (0.0.0.0:8096), gates G1-G3,
# coder_eval.sh on .194 (IKP + HumanEval+), M1 from the desktop for CODER only, stop. Resumable per arm (DONE marker).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; QA="$HERE/../quant-abstention"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8096; URL="http://$H:$PORT"
BIN='~/buun-0b278/build_sm60/bin/llama-server'
declare -A MODEL=([CODER]='AI/Models/fn_gsq_coder/Qwen3.8-Flash-Next-GSQ-RCO-IQ1_M-00001-of-00002.gguf'
                  [FNGB]='AI/Models/fn_gsq_base/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf')
declare -A NEXP=([CODER]=256 [FNGB]=512)
FLAGS="-ngl 99 -sm layer -ts 1,1,1,0.6 -c 8192 -fa on -np 1 --no-cache-prompt --jinja -ctk f16 -ctv f16 -fit off -lv 4 --host 0.0.0.0 --port $PORT"
KW='{"reasoning_effort":"medium","enable_thinking":false}'
VAR='{" UNKNOWN": 59322, " Unknown": 21024, " unknown": 9496}'
OUT="$HERE/raw"; mkdir -p "$OUT"; LOG="$OUT/run.log"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
R() { timeout "${2:-60}" ssh -n -o BatchMode=yes "$H" "$1"; }
stop_server() { R 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' 90 \
                || { log "a llama-server survived pkill -- aborting"; exit 1; }; }
trap 'stop_server' EXIT

log "== coder-prune start"
R 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u' | tee -a "$LOG"
# G3a: the Coder's shard 1 must be the manifest's file
R "grep -q 'OK Qwen3.8-Flash-Next-GSQ-RCO-IQ1_M-00001-of-00002.gguf' ~/AI/Models/coder_fetch.log" || { log "G3 FAIL: Coder shard 1 not fetched+verified"; exit 1; }
for ARM in CODER FNGB; do
  R "test -f ~/reapfn/out_coder/$ARM.DONE" && { log "$ARM eval done, skipped"; [ "$ARM" = CODER ] && [ -s "$QA/raw/main_CODER.jsonl" ] && continue; }
  stop_server
  R "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal setsid nohup $BIN -m ~/${MODEL[$ARM]} $FLAGS --chat-template-kwargs '$KW' > ~/coder_$ARM.log 2>&1 < /dev/null & echo started" 20
  up=0
  for i in $(seq 1 120); do
    sleep 5
    R 'pgrep -x llama-server >/dev/null' || { log "$ARM: server died: $(R "tail -3 ~/coder_$ARM.log")"; exit 1; }
    R "grep -q 'model loaded' ~/coder_$ARM.log" && curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }
  done
  [ $up = 1 ] || { log "$ARM: not healthy"; exit 1; }
  # G1: file, expert count, placement; G3b: q2_0 g64, no Bonsai remap; G2: thinking off
  mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "${MODEL[$ARM]}")" ] || { log "$ARM: WRONG SERVER $mp"; exit 1; }
  ne=$(R "grep -o -m1 'n_expert *= *[0-9]*' ~/coder_$ARM.log | grep -o '[0-9]*$'")
  [ "$ne" = "${NEXP[$ARM]}" ] || { log "$ARM: G1 n_expert $ne != ${NEXP[$ARM]}"; exit 1; }
  R "grep -q 'offloaded 49/49 layers to GPU' ~/coder_$ARM.log" || { log "$ARM: G1 placement not 49/49"; exit 1; }
  R "grep -q 'detected PrismML Bonsai group-128' ~/coder_$ARM.log" && { log "$ARM: G3 FAIL Bonsai remap fired"; exit 1; }
  g2=$(curl -s -m 600 "$URL/v1/chat/completions" -H 'content-type: application/json' -d '{"messages":[{"role":"user","content":"What is the capital of France?"}],"max_tokens":32,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}' >/dev/null; \
       curl -s -m 600 "$URL/v1/chat/completions" -H 'content-type: application/json' -d '{"messages":[{"role":"user","content":"What is the capital of France?"}],"max_tokens":32,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}' \
       | $PY -c 'import json,sys; m=json.load(sys.stdin)["choices"][0]["message"]; print("ok" if (m.get("content") or "").strip() and not (m.get("reasoning_content") or "").strip() else "FAIL", repr((m.get("content") or "")[:40]))')
  case "$g2" in ok*) ;; *) log "$ARM: G2 FAIL $g2"; exit 1;; esac
  log "$ARM: verified -- $(basename "$mp"), n_expert $ne, 49/49, q2_0: $(R "grep -o 'type *q2_0: *[0-9]* tensors' ~/coder_$ARM.log | head -1"), G2 $g2"
  if ! R "test -f ~/reapfn/out_coder/$ARM.DONE"; then
    scp -q "$HERE/coder_eval.sh" "$H:reapfn/coder_eval.sh"
    R "chmod +x ~/reapfn/coder_eval.sh; setsid nohup ~/reapfn/coder_eval.sh $ARM > ~/reapfn/coder_eval_$ARM.log 2>&1 < /dev/null & echo launched" 20 | tee -a "$LOG"
    until R "test -f ~/reapfn/out_coder/$ARM.DONE"; do sleep 60; R "pgrep -x llama-server >/dev/null" || { log "$ARM: server died mid-eval"; exit 1; }; done
    log "$ARM: eval done: $(R "cat ~/reapfn/out_coder/$ARM/progress.txt | tr '\n' ' '")"
  fi
  if [ "$ARM" = CODER ]; then
    meta=$($PY -c 'import json,sys; print(json.dumps({"arm":"CODER","model":sys.argv[1],"build":"buun 0b2789f23 build_sm60","host":".194 4x P100 150 W / 1063 MHz","flags":sys.argv[2]}))' "$(basename "${MODEL[$ARM]}")" "$FLAGS")
    log "CODER: M1"
    (cd "$QA" && $PY run_main.py --url "$URL" --arm CODER --meta "$meta" --expect-variants "$VAR") >> "$OUT/m1_CODER.log" 2>&1
    log "CODER: M1 exit $? ($(($(wc -l < "$QA/raw/main_CODER.jsonl") - 1)) rows)"
  fi
  mkdir -p "$OUT/$ARM"; scp -q -r "$H:reapfn/out_coder/$ARM/." "$OUT/$ARM/"; scp -q "$H:coder_$ARM.log" "$OUT/$ARM/server.log" 2>/dev/null
  stop_server
done
log "== coder-prune done"
