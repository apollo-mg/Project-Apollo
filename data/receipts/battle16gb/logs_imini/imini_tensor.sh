#!/usr/bin/env bash
# GAP IN THE PREVIOUS TEST: I tested `-sm row` and treated it as "the tensor split". It is not.
# This build offers {none,layer,row,tensor} and `tensor` is a DIFFERENT, newer implementation.
# `row` was rejected instantly on P100 ("device CUDA0 does not support split buffers"); `tensor`
# may not be. Testing the mode that was actually asked about.
set -u
exec 9>/home/mark/.imini_tensor.lock
flock -n 9 || { echo "already running"; exit 3; }
BIN=/home/mark/llama_stock_ref/build_puzzle73/bin
MODEL=/mnt/models/APEX/Nemotron-Labs-3-Puzzle-75B-A9B-APEX-i-mini.gguf
OUT=/home/mark/imini_tensor
rm -rf "$OUT"; mkdir -p "$OUT"
LOG=$OUT/tensor.log
PORT=8095
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
try(){
	local tag=$1; shift
	local slog=$OUT/server_${tag}.log
	say "########## $tag : $* ##########"
	if pgrep -x llama-server >/dev/null; then say "  ABORT: server alive"; return 9; fi
	LD_LIBRARY_PATH="$BIN" setsid "$BIN/llama-server" -m "$MODEL" -ngl 99 -fa on "$@" \
		-np 1 --host 127.0.0.1 --port "$PORT" --jinja > "$slog" 2>&1 < /dev/null &
	local pid=$! ok=0 i
	for i in $(seq 1 600); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" != 1 ]; then
		say "  NO LOAD:"
		grep -oiE "does not support[^\"]{0,40}|allocating [0-9.]+ MiB on device [0-9]|GGML_ASSERT[^\"]{0,70}|failed to allocate [A-Za-z0-9 ]{0,25}" "$slog" | sort -u | head -3 | sed 's/^/      /' | tee -a "$LOG"
		kill -9 "$pid" 2>/dev/null; sleep 10; return 1
	fi
	say "  *** LOADED *** vram=[$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB' | tr '\n' ' ')] / [16269 16269]"
	curl -s -m 900 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
		-d '{"model":"q","temperature":0,"max_tokens":32,"cache_prompt":false,"messages":[{"role":"user","content":"Hi."}]}' >/dev/null 2>&1
	curl -s -m 900 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
		-d '{"model":"q","temperature":0,"max_tokens":150,"cache_prompt":false,"messages":[{"role":"user","content":"Write a Python function returning the nth Fibonacci number."}]}' \
		> "$OUT/gen_${tag}.json" 2>/dev/null
	python3 - "$slog" "$tag" "$OUT" <<'PY' | tee -a "$LOG"
import sys,re,json,gzip,os
slog,tag,out=sys.argv[1],sys.argv[2],sys.argv[3]
dec=[float(m.group(2)) for m in (re.search(r"eval time =\s*[\d.]+ ms /\s*(\d+) tokens \(\s*[\d.]+ ms per token,\s*([\d.]+) tokens per second",l) for l in open(slog,errors='replace') if "prompt eval time" not in l) if m]
p=f"{out}/gen_{tag}.json"; gz=None; ok=False
if os.path.exists(p) and os.path.getsize(p):
    try:
        m=json.load(open(p))["choices"][0]["message"]
        s=(m.get("content") or "")+(m.get("reasoning_content") or "")
        if s.strip(): gz=round(len(gzip.compress(s.encode(),6))/len(s.encode()),4); ok=True
    except Exception: pass
print(f"    {tag:<18} decode={dec[-1] if dec else 'n/a'} t/s  generated={ok}  gzip={gz}")
PY
	kill "$pid" 2>/dev/null
	local w; for w in $(seq 1 60); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 10
	return 0
}
say "===== i-mini with -sm tensor (the mode NOT tested before) ====="
try "tensor_c2048" -sm tensor -c 2048 -ctk q8_0 -ctv q8_0
try "tensor_c4096" -sm tensor -c 4096 -ctk q8_0 -ctv q8_0
try "tensor_c8192" -sm tensor -c 8192 -ctk q8_0 -ctv q8_0
say "===== TENSOR TEST DONE ====="
