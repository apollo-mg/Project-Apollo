#!/usr/bin/env bash
# Is i-mini's OOM a split-BALANCE problem rather than a capacity problem?
#
# EVIDENCE IT IS: with -sm layer -ts 1,1, dropping context 8192 -> 4096 (and f16 -> q8_0 KV)
# changed nothing, and the terminal failure is allocating *140 MiB* on device 0. Device 0 is full
# of weights; KV size is not the lever.
#
# WHY PUZZLE IS THE WORST CASE FOR LAYER SPLIT: it is a NAS-derived heterogeneous model -- 7
# distinct per-layer top-k values, per-layer n_ff_exp, and mixed mamba2/attention/MoE blocks. So
# `-ts 1,1` under -sm layer equalises LAYER COUNT, not BYTES. Tensor/row split shards each tensor
# across devices, balancing by construction.
#
# Arms walk from "let llama.cpp decide" to "shard every tensor" to "manually bias layers off the
# full card". Any arm that loads gets a generation check -- allocating is not fitting.
set -u
exec 9>/home/mark/.imini_split.lock
flock -n 9 || { echo "already running"; exit 3; }
BIN=/home/mark/llama_stock_ref/build_puzzle73/bin
MODEL=/mnt/models/APEX/Nemotron-Labs-3-Puzzle-75B-A9B-APEX-i-mini.gguf
OUT=/home/mark/imini_split
rm -rf "$OUT"; mkdir -p "$OUT"
LOG=$OUT/split.log
PORT=8094
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

# $1 tag, $2 args
try(){
	local tag=$1; shift
	local slog=$OUT/server_${tag}.log
	say "########## $tag : $* ##########"
	if pgrep -x llama-server >/dev/null; then say "  ABORT: server alive"; return 9; fi
	LD_LIBRARY_PATH="$BIN" setsid "$BIN/llama-server" -m "$MODEL" \
		-c 2048 -ngl 99 -fa on -ctk q8_0 -ctv q8_0 "$@" \
		-np 1 --host 127.0.0.1 --port "$PORT" --jinja -lv 1 > "$slog" 2>&1 < /dev/null &
	local pid=$! ok=0 i
	for i in $(seq 1 600); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" != 1 ]; then
		say "  NO LOAD:"
		grep -oiE "allocating [0-9.]+ MiB on device [0-9]|failed to allocate [A-Za-z0-9 ]{0,30}|GGML_ASSERT[^\"]{0,70}" "$slog" \
			| sort -u | head -3 | sed 's/^/      /' | tee -a "$LOG"
		kill -9 "$pid" 2>/dev/null; sleep 10; return 1
	fi
	local vram; vram=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB' | tr '\n' ' ')
	say "  *** LOADED *** vram=[$vram] / [16269 16269] MiB"
	curl -s -m 900 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
		-d '{"model":"q","temperature":0,"max_tokens":32,"cache_prompt":false,"messages":[{"role":"user","content":"Hi."}]}' >/dev/null 2>&1
	curl -s -m 900 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
		-d '{"model":"q","temperature":0,"max_tokens":150,"cache_prompt":false,"messages":[{"role":"user","content":"Write a Python function returning the nth Fibonacci number."}]}' \
		> "$OUT/gen_${tag}.json" 2>/dev/null
	python3 - "$slog" "$tag" "$OUT" <<'PY' | tee -a "$LOG"
import sys,re,json,gzip,os
slog,tag,out=sys.argv[1],sys.argv[2],sys.argv[3]
dec=[t for n,t in (( int(m.group(1)),float(m.group(2)) ) for m in
    (re.search(r"eval time =\s*[\d.]+ ms /\s*(\d+) tokens \(\s*[\d.]+ ms per token,\s*([\d.]+) tokens per second",l)
     for l in open(slog,errors='replace') if "prompt eval time" not in l) if m)]
p=f"{out}/gen_{tag}.json"; gz=None; ok=False
if os.path.exists(p) and os.path.getsize(p):
    try:
        m=json.load(open(p))["choices"][0]["message"]
        s=(m.get("content") or "")+(m.get("reasoning_content") or "")
        if s.strip(): gz=round(len(gzip.compress(s.encode(),6))/len(s.encode()),4); ok=True
    except Exception: pass
print(f"    {tag:<16} decode={dec[-1] if dec else 'n/a'} t/s  generated={ok}  gzip={gz}")
PY
	kill "$pid" 2>/dev/null
	local w; for w in $(seq 1 60); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 10
	return 0
}

say "===== i-mini split-mode test (all arms -c 2048 -ctk/-ctv q8_0) ====="
say "baseline already failed: -sm layer -ts 1,1 OOMs at 140 MiB on device 0"
try "auto"        # no -sm, no -ts: llama.cpp's own proportional split
try "row"      -sm row          # tensor/row split -- shards each tensor
try "layer_46" -sm layer -ts 4,6   # bias layers OFF device 0
try "layer_37" -sm layer -ts 3,7
say "===== SPLIT TEST DONE ====="
say "READ: if row/auto load where layer 1,1 did not, the wall was BALANCE, not capacity."
