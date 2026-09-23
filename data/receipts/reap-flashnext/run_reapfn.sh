#!/bin/bash
# REAP on Flash-Next, knowledge (IKP) + code (HumanEval+). Runs ON .194. PREREG_REAP_FLASHNEXT.md
#   ./run_reapfn.sh ARM [ARM...]   ARM in FULLQ2 R320Q2 IQ4XS D27Q6 R320Q3 IQ1S
# Resumable: ikp_run.py resumes its JSONL; an arm whose hep json exists is skipped for code.
# PROCESS RULE: kills only the server PID it recorded. Does NOT touch the desktop benchmark lock.
set -u
W=~/reapfn                      # ikp/ + humaneval-plus/ copied here from the repo
S=~/buun-llama-cpp/build_sm60_0920/bin/llama-server   # buun 08826ad6e
M=~/AI/Models
PORT=8096
export GGML_CUDA_ALLREDUCE=internal   # NCCL default aborts on .194
mkdir -p "$W/out"

model_of () { case $1 in
  FULLQ2) echo "$M/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf 512";;
  R320Q2) echo "$M/flash_next_reap320_q2/Q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-reap320-00001-of-00002.gguf 320";;
  R320Q3) echo "$M/flash_next_reap320_q3/Qwen3.8-Flash-Next-UD-Q3_K_XL-reap320-00001-of-00002.gguf 320";;
  IQ1S)   echo "$M/flashnext_iq1s/UD-IQ1_S/Qwen3.8-Flash-Next-UD-IQ1_S-00001-of-00003.gguf 512";;
  IQ4XS)  echo "$M/flashnext/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf 512";;
  D27Q6)  echo "$M/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf 0";;
  *) echo ""; esac; }

SRVPID=""
stop () { [ -n "$SRVPID" ] || return 0; kill "$SRVPID" 2>/dev/null
  for i in $(seq 1 40); do kill -0 "$SRVPID" 2>/dev/null || break; sleep 1; done
  kill -0 "$SRVPID" 2>/dev/null && kill -9 "$SRVPID"; SRVPID=""; sleep 5; }
trap stop EXIT

verify_sha () {  # G3 for the late arms: local sha256 must equal the upstream LFS oid
  local dir=$1 exp=$2
  [ -f "$dir/SHA256SUMS.txt" ] || { echo "G3 FAIL: no SHA256SUMS in $dir (download/hash not finished)"; return 1; }
  while read -r h f; do
    grep -q "^$h  .*$(basename "$f")$" "$dir/SHA256SUMS.txt" || { echo "G3 FAIL: $f"; return 1; }
  done < "$exp"; echo "G3 ok: $dir"; }

for ARM in "$@"; do
  read -r MODEL NEXP <<< "$(model_of "$ARM")"
  [ -n "$MODEL" ] || { echo "unknown arm $ARM"; exit 2; }
  O="$W/out/$ARM"; mkdir -p "$O"
  case $ARM in
    R320Q3) verify_sha "$M/flash_next_reap320_q3" "$W/expected_r320q3.sha" || exit 3;;
    IQ1S)   verify_sha "$M/flashnext_iq1s" "$W/expected_iq1s.sha" || exit 3;;
  esac
  echo "######## $ARM $(date -Is)"
  nvidia-smi --query-gpu=index,clocks.sm,clocks.max.sm,power.limit,temperature.gpu --format=csv,noheader > "$O/clocks_start.txt"
  curl -s -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { echo "ABORT: :$PORT already in use"; exit 1; }
  "$S" -m "$MODEL" -ngl 99 -sm layer -c 8192 -fa on -np 1 --no-cache-prompt --jinja -v \
      --chat-template-kwargs '{"reasoning_effort":"medium","enable_thinking":false}' \
      --host 127.0.0.1 --port "$PORT" > "$O/server.log" 2>&1 < /dev/null &
  SRVPID=$!; echo "$SRVPID" > "$O/server.pid"
  for i in $(seq 1 300); do curl -sf -m 2 "http://127.0.0.1:$PORT/health" >/dev/null && break
    kill -0 "$SRVPID" 2>/dev/null || { echo "ABORT: $ARM server died"; tail -5 "$O/server.log"; exit 1; }; sleep 2; done
  # G1: model path, expert count, all layers on GPU -- from the runtime's own output
  python3 - "$PORT" "$MODEL" "$NEXP" "$O/server.log" <<'PY' || { echo "ABORT: $ARM G1/G2 failed"; exit 1; }
import json, re, sys, urllib.request
port, model, nexp, log = sys.argv[1], sys.argv[2], int(sys.argv[3]), open(sys.argv[4]).read()
p = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/props", timeout=30))
assert p["model_path"].endswith(model.split("/")[-1]), p["model_path"]
if nexp:
    m = re.search(r"n_expert\s*=\s*(\d+)", log); assert m and int(m[1]) == nexp, (m and m[1], nexp)
off = re.search(r"offloaded (\d+)/(\d+) layers to GPU", log); assert off and off[1] == off[2], off and off.group(0)
# G2: rendered prompt carries no effort block and thinking is off (reasoning_content empty)
body = json.dumps({"messages": [{"role": "user", "content": "What is the capital of France?"}], "max_tokens": 32,
                   "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}).encode()
rq = lambda path, b: json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}{path}", b,
                                {"Content-Type": "application/json"}), timeout=300))
for i in range(2):   # first = warmup (discarded), second = the G2 check
    r = rq("/v1/chat/completions", body)
msg = r["choices"][0]["message"]
assert not (msg.get("reasoning_content") or "").strip(), "thinking fired"
assert msg.get("content", "").strip(), "empty content"
print(f"G1/G2 ok: {off.group(0)}, n_expert={nexp or 'dense'}, reply={msg['content'].strip()[:40]!r}")
PY
  # knowledge
  ( cd "$W/ikp" && python3 ikp_run.py --endpoint "http://127.0.0.1:$PORT" --label "$ARM" --out "$O/ikp.jsonl" \
      --tiers T1,T2,T3,T4 --max-tokens 64 --no-think --exclude-source researcher ) > "$O/ikp.log" 2>&1
  echo "   ikp rows=$(wc -l < "$O/ikp.jsonl")"
  # code
  if ! ls "$O"/hep_*.json >/dev/null 2>&1; then
    ( cd "$W/humaneval-plus" && HEP_ENDPOINT="http://127.0.0.1:$PORT/v1/chat/completions" HEP_MODEL="$ARM" \
        HEP_TEMP=0 HEP_K=1 HEP_THINK=0 HEP_MAXTOK=4096 HEP_PREFIX="$O/hep" python3 hep_eval.py ) > "$O/hep.log" 2>&1
    tail -3 "$O/hep.log"
  fi
  nvidia-smi --query-gpu=index,clocks.sm,clocks.max.sm,power.limit,temperature.gpu --format=csv,noheader > "$O/clocks_end.txt"
  stop
done
echo "######## REAPFN DONE $(date -Is)"
