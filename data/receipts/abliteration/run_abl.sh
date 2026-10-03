#!/usr/bin/env bash
# PREREG_ABLITERATION_CALIB.md runner (desktop -> .194). Usage: run_abl.sh 1|2
#   wave 1: U6 on half A, S6 on half B (parallel); then KLD reference logits from U6 and S6's KLD (half A).
#   wave 2: U4s on A, U4x on B (parallel); then their KLDs (A and B in parallel).
# Halves: A = GPUs 0,1 + socket 0, port 8191; B = GPUs 2,3 + socket 1, port 8192. Servers are stopped by their
# recorded PIDs only (two run at once: never pkill by name). Resumable per arm (DONE marker in raw/<ARM>/).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; R_="$HERE/.."; PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; B='~/buun-0b278/build_sm60/bin'; D='~/AI/Models/abl'
declare -A FILE=([S6]=Qwen3.8-27B-Q6_K.gguf [U6]=Qwen3.8-27B-Uncensored-Q6_K.gguf [U4s]=OrcaSAQ-2-27B-Uncensored.gguf [U4x]=Qwen3.8-27B-Uncensored-IQ4_XS.gguf)
declare -A GPU=([A]=0,1 [B]=2,3) NODE=([A]=0 [B]=1) PORT=([A]=8191 [B]=8192)
FLAGS="-ngl 99 -sm layer -fit off -fa on -c 8192 -np 1 --no-cache-prompt --jinja -ctk f16 -ctv f16 -lv 4 --host 0.0.0.0"
KW='{"reasoning_effort":"medium","enable_thinking":false}'
VAR='{" UNKNOWN": 59322, " Unknown": 21024, " unknown": 9496}'
PF="-ngl 99 -sm layer -fit off -fa on -c 512 --chunks 16 -ctk f16 -ctv f16 -lv 4"
OUT="$HERE/raw"; mkdir -p "$OUT"; LOG="$OUT/run.log"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
R() { timeout "${2:-60}" ssh -n -o BatchMode=yes "$H" "$1"; }
stop_half() {  # stop the server of half $1 by its recorded PID
  R "p=\$(cat ~/abl_$1.pid 2>/dev/null); [ -n \"\$p\" ] && kill \$p 2>/dev/null; for i in \$(seq 1 60); do [ -n \"\$p\" ] && kill -0 \$p 2>/dev/null || exit 0; sleep 1; done; exit 1" 90 \
    || { log "half $1: server survived kill"; return 1; }
}

run_arm() {  # ARM HALF
  local a=$1 h=$2 url="http://$H:${PORT[$2]}" o="$OUT/$1"
  mkdir -p "$o"; [ -f "$o/DONE" ] && { log "$a done, skipped"; return 0; }
  stop_half $h
  R "CUDA_VISIBLE_DEVICES=${GPU[$h]} setsid nohup numactl --cpunodebind=${NODE[$h]} --preferred=${NODE[$h]} $B/llama-server -m $D/${FILE[$a]} $FLAGS --port ${PORT[$h]} --chat-template-kwargs '$KW' > ~/abl_$a.log 2>&1 < /dev/null & echo \$! > ~/abl_$h.pid" 20
  local up=0
  for i in $(seq 1 120); do sleep 5
    R "kill -0 \$(cat ~/abl_$h.pid) 2>/dev/null" || { log "$a: server died: $(R "grep -i -E 'error|fail' ~/abl_$a.log | tail -2")"; return 1; }
    curl -sf -m 5 "$url/health" >/dev/null && { up=1; break; }
  done
  [ $up = 1 ] || { log "$a: not healthy"; return 1; }
  # gates
  local mp off vbr g2 tok
  mp=$(curl -s -m 5 "$url/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "${FILE[$a]}" ] || { log "$a: WRONG MODEL $mp"; return 1; }
  off=$(R "grep -o -m1 'offloaded [0-9]*/[0-9]* layers to GPU' ~/abl_$a.log")
  echo "$off" | $PY -c 'import re,sys; m=re.search(r"(\d+)/(\d+)", sys.stdin.read()); sys.exit(0 if m and m.group(1)==m.group(2) else 1)' || { log "$a: placement '$off'"; return 1; }
  vbr=$(R "grep -c 'VBR dynamic' ~/abl_$a.log")
  [ "$vbr" = 0 ] || { log "$a: VBR KV active"; return 1; }
  g2=$(curl -s -m 600 "$url/v1/chat/completions" -H 'content-type: application/json' -d '{"messages":[{"role":"user","content":"What is the capital of France?"}],"max_tokens":32,"temperature":0}' \
       | $PY -c 'import json,sys; m=json.load(sys.stdin)["choices"][0]["message"]; print("ok" if (m.get("content") or "").strip() and not (m.get("reasoning_content") or "").strip() else "FAIL", repr((m.get("content") or "")[:30]))')
  case "$g2" in ok*) ;; *) log "$a: G2 FAIL $g2"; return 1;; esac
  tok=$(for t in " UNKNOWN" " Unknown" " unknown"; do curl -s -m 10 "$url/tokenize" -H 'content-type: application/json' -d "{\"content\":\"$t\"}" | $PY -c 'import json,sys; print(json.load(sys.stdin)["tokens"])'; done | tr '\n' ' ')
  [ "$tok" = "[59322] [21024] [9496] " ] || { log "$a: UNKNOWN token ids differ: $tok"; return 1; }
  log "$a ($h): verified -- ${FILE[$a]}, $off, f16 KV, G2 $g2, UNKNOWN ids ok"
  # IKP then M1
  (cd "$R_/ikp" && $PY ikp_run.py --endpoint "$url" --label "ABL_$a" --out "$o/ikp.jsonl" --tiers T1,T2,T3,T4 --max-tokens 64 \
     --no-think --exclude-source researcher) > "$o/ikp.log" 2>&1
  log "$a: IKP exit $? rows $(wc -l < "$o/ikp.jsonl")"
  local meta; meta=$($PY -c 'import json,sys; print(json.dumps({"arm":sys.argv[1],"model":sys.argv[2],"build":"buun 0b2789f23 build_sm60","host":".194 half "+sys.argv[3]+" (2x P100)","flags":sys.argv[4]}))' "ABL_$a" "${FILE[$a]}" "$h" "$FLAGS")
  (cd "$R_/quant-abstention" && $PY run_main.py --url "$url" --arm "ABL_$a" --meta "$meta" --expect-variants "$VAR") > "$o/m1.log" 2>&1
  log "$a: M1 exit $?"
  cp "$R_/quant-abstention/raw/main_ABL_$a.jsonl" "$o/m1.jsonl"
  scp -q "$H:abl_$a.log" "$o/server.log" 2>/dev/null
  stop_half $h
  touch "$o/DONE"
}

kld() {  # ARM HALF [base]
  local a=$1 h=$2 f="$OUT/kld_$1.txt"
  [ -s "$f" ] && grep -q 'Mean    KLD\|Final estimate' "$f" && { log "kld $a done, skipped"; return 0; }
  stop_half $h
  local extra="--kl-divergence-base ~/abl_kld_base.bin --kl-divergence"; [ "${3:-}" = base ] && extra="--kl-divergence-base ~/abl_kld_base.bin"
  R "CUDA_VISIBLE_DEVICES=${GPU[$h]} numactl --cpunodebind=${NODE[$h]} --preferred=${NODE[$h]} $B/llama-perplexity -m $D/${FILE[$a]} $PF -f ~/wikitext-2-raw/wiki.test.raw $extra" 1800 > "$f" 2>&1
  log "kld $a: exit $?; $(grep -E 'Mean +KLD|Final estimate' "$f" | head -1)"
}

case "${1:-}" in
  1) log "== wave 1"; run_arm U6 A & PA=$!; run_arm S6 B & PB=$!; wait $PA; wait $PB
     kld U6 A base; kld S6 A ;;
  2) log "== wave 2"; run_arm U4s A & PA=$!; run_arm U4x B & PB=$!; wait $PA; wait $PB
     kld U4s A & KA=$!; kld U4x B & KB=$!; wait $KA; wait $KB ;;
  *) echo "usage: $0 1|2"; exit 2 ;;
esac
log "== wave ${1} done"
