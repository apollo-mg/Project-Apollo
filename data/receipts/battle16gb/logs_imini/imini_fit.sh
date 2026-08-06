#!/usr/bin/env bash
# Does APEX i-mini (75B Puzzle @ 2.94 bpw) fit in 32 GB of 2016-era VRAM?
#
# THE ARITHMETIC: i-mini is 31.0 GB = 28.9 GiB. Two P100s give 2 x 16269 MiB = 31.77 GiB usable.
# That leaves ~2.87 GiB for KV cache + compute buffers. Tight but not obviously impossible.
#
# BUILD: ~/llama_stock_ref/build_puzzle73 @ adeff9b82 (upstream PR #25444 head), CUDA arch 60.
# This is STOCK llama.cpp + PR -- no TurboQuant, so no turbo3 KV. KV options are f16/q8_0/q4_0.
# The sm_60 FAST_FP16 carveout is deliberately NOT applied (preserved on branch
# sm60-carveout-73) so results stay comparable to leg W3's .194 binary.
#
# LADDER: walk from most-demanding to least. Stop at the first configuration that loads and
# generates. Report VRAM per card at each step -- the number that says how close to the wall it is.
set -u
exec 9>/home/mark/.imini_fit.lock
flock -n 9 || { echo "already running"; exit 3; }
BIN=/home/mark/llama_stock_ref/build_puzzle73/bin
MODEL=/mnt/models/APEX/Nemotron-Labs-3-Puzzle-75B-A9B-APEX-i-mini.gguf
OUT=/home/mark/imini_fit
rm -rf "$OUT"; mkdir -p "$OUT"
LOG=$OUT/fit.log
PORT=8093
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

# $1 tag, $2 ctx, $3 kv-type, $4 extra
try(){
	local tag=$1 ctx=$2 kv=$3 extra=${4:-}
	local slog=$OUT/server_${tag}.log
	say "########## $tag : -c $ctx -ctk $kv -ctv $kv ${extra:-} ##########"
	if pgrep -x llama-server >/dev/null; then say "  ABORT: server alive"; return 9; fi
	# shellcheck disable=SC2086
	LD_LIBRARY_PATH="$BIN" setsid "$BIN/llama-server" -m "$MODEL" \
		-c "$ctx" -ngl 99 -sm layer -ts 1,1 -fa on -ctk "$kv" -ctv "$kv" $extra \
		-np 1 --host 127.0.0.1 --port "$PORT" --jinja > "$slog" 2>&1 < /dev/null &
	local pid=$! ok=0 i
	for i in $(seq 1 600); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" != 1 ]; then
		say "  NO LOAD:"
		grep -oiE "failed to allocate[^\"]{0,70}|out of memory[^\"]{0,40}|cudaMalloc[^\"]{0,50}|GGML_ASSERT[^\"]{0,80}|unknown model architecture[^\"]{0,40}|expert_used_count[^\"]{0,60}" "$slog" \
			| sort -u | head -3 | sed 's/^/      /' | tee -a "$LOG"
		kill -9 "$pid" 2>/dev/null; sleep 10; return 1
	fi
	local vram; vram=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB' | tr '\n' ' ')
	say "  *** LOADED *** vram=[$vram] of [16269 16269] MiB"
	# Prove it generates, not just allocates. Warm first (cold reads come off disk).
	curl -s -m 900 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
		-d '{"model":"q","temperature":0,"max_tokens":64,"cache_prompt":false,"messages":[{"role":"user","content":"Say hello."}]}' >/dev/null 2>&1
	curl -s -m 900 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
		-d '{"model":"q","temperature":0,"max_tokens":200,"cache_prompt":false,"messages":[{"role":"user","content":"Write a Python function that returns the nth Fibonacci number."}]}' \
		> "$OUT/gen_${tag}.json" 2>/dev/null
	python3 - "$slog" "$tag" "$OUT" <<'PY' | tee -a "$LOG"
import sys,re,json,gzip,os
slog,tag,out=sys.argv[1],sys.argv[2],sys.argv[3]
dec=[]
for line in open(slog,errors='replace'):
    m=re.search(r"eval time =\s*[\d.]+ ms /\s*(\d+) tokens \(\s*[\d.]+ ms per token,\s*([\d.]+) tokens per second",line)
    if m and "prompt eval time" not in line: dec.append((int(m.group(1)),float(m.group(2))))
p=f"{out}/gen_{tag}.json"; gz=None; ok=False
if os.path.exists(p) and os.path.getsize(p):
    try:
        msg=json.load(open(p))["choices"][0]["message"]
        s=(msg.get("content") or "")+(msg.get("reasoning_content") or "")
        if s.strip():
            gz=round(len(gzip.compress(s.encode(),6))/len(s.encode()),4); ok=True
    except Exception: pass
print(f"    {tag:<14} decode={dec[-1][1] if dec else 'n/a'} t/s  generated={ok}  gzip={gz}")
PY
	kill "$pid" 2>/dev/null
	local w; for w in $(seq 1 60); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 10
	return 0
}

say "===== APEX i-mini VRAM fit test on 2x P100 (31.77 GiB usable) ====="
say "model: 31.0 GB = 28.9 GiB -> ~2.87 GiB left for KV + buffers"
say "build: adeff9b82 (PR #25444), stock llama.cpp, no turbo3 KV available"
try "c8192_f16"  8192  f16
try "c8192_q8"   8192  q8_0
try "c4096_q8"   4096  q8_0
try "c2048_q8"   2048  q8_0
try "c2048_q4"   2048  q4_0
say "===== FIT TEST DONE ====="
