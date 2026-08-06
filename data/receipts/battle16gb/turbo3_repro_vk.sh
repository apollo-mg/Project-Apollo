#!/usr/bin/env bash
# Cross-backend check on TheTom/llama-cpp-turboquant#241:
#   "turbo3 V-cache produces corrupted output, turbo2 and turbo4 are correct"
#
# THEIR REPORT (suhermanme, 2026-07-30): RX 580, **Vulkan/RADV**, turboquant 9953 (30d6881eb),
# Qwen3.6-35B-A3B Q4_K_M, -ctk turbo4 -ctv turbo3, -c 256000, --n-cpu-moe 36.
# Output degenerates into repeated CJK punctuation: "。，。，。，。，..." -- classic degenerate
# repetition, i.e. the sampler is being fed a broken distribution.
# f16 OK, turbo2 OK, turbo4 OK, turbo3 CORRUPTED.
#
# WHAT THIS RUN IS AND IS NOT.
# NOT a replication: we are on **HIP/ROCm, RDNA4 (gfx1201)**, they are on Vulkan/RADV, Polaris.
# Different kernels entirely. That is exactly why it is worth running:
#   turbo3 broken here too  -> codec-level bug, affects every backend, high priority for Tom
#   turbo3 clean here       -> bug is in the RADV/Vulkan turbo3 path specifically
# Either outcome is a useful, decisive datum on an open issue.
#
# Also differs: our model is IQ2_M not Q4_K_M (weights quant), and we do not use --n-cpu-moe.
# The codec under test is the KV cache, not the weights, so this is a fair test of turbo3 --
# but any NEGATIVE result must be reported with these deltas stated.
#
# METHOD. Their failure is degenerate repetition, which is a fidelity failure -- so it does not
# require reproducing their serving config. Two probes per cell:
#   1. generation probe: fixed prompt, temp 0, look for degenerate output directly
#   2. compression ratio: gzip(text)/len(text). Degenerate repetition compresses absurdly well.
#      "。，。，。，..." lands near 0.02-0.05; healthy English prose is ~0.35-0.45.
# The gzip metric is the objective gate -- eyeballing output is how you miss a subtle failure.
set -u
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build_vulkan/bin
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/35B-A3B/Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
OUT=/home/mark/projects/HermesAgent-20/turbo3_repro_vk
PORT=${PORT:-8122}
mkdir -p "$OUT"
LOG=$OUT/repro.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
export LD_LIBRARY_PATH="$BIN:${LD_LIBRARY_PATH:-}"

cat > "$OUT/probe.json" <<'EOF'
{"model":"q","temperature":0,"max_tokens":500,"cache_prompt":false,
 "messages":[{"role":"user","content":"Write a 500-word essay about Linux."}]}
EOF

cell() {
	local ctk=$1 ctv=$2
	local tag="k${ctk}_v${ctv}"
	local slog=$OUT/server_${tag}.log
	say "--- cell -ctk $ctk -ctv $ctv ---"
	setsid "$BIN/llama-server" -m "$MODEL" -c 16384 -b 1024 -ub 512 \
		-ctk "$ctk" -ctv "$ctv" -fa on -np 1 -ngl 99 --cache-ram 0 \
		--port "$PORT" --host 127.0.0.1 --jinja \
		> "$slog" 2>&1 < /dev/null &
	local pid=$! ok=0 i
	for i in $(seq 1 150); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" != 1 ]; then
		say "  SERVER FAILED TO START (this is itself a result)"
		grep -iE "error|unsupported|abort|assert" "$slog" | tail -3 | sed 's/^/    /' | tee -a "$LOG"
		kill -9 "$pid" 2>/dev/null; sleep 5; return
	fi
	curl -s -m 300 "http://127.0.0.1:$PORT/v1/chat/completions" \
		-H 'Content-Type: application/json' -d @"$OUT/probe.json" > "$OUT/resp_${tag}.json"
	python3 - "$OUT/resp_${tag}.json" "$tag" <<'PY' | tee -a "$LOG"
import json,sys,gzip,re
p,tag=sys.argv[1],sys.argv[2]
try:
    d=json.load(open(p)); m=d["choices"][0]["message"]
    t=(m.get("content") or "")+(m.get("reasoning_content") or "")
except Exception as e:
    print("    %s PARSE FAIL %s"%(tag,e)); raise SystemExit
b=t.encode("utf-8","ignore")
ratio=len(gzip.compress(b,6))/max(len(b),1)
# CJK punctuation run: the exact signature in the issue
worst=max((len(x) for x in re.findall(r'([。，、°]\s*){3,}',t)), default=0) if t else 0
runs=re.findall(r'[。，、°]{3,}',t)
verdict="DEGENERATE" if ratio<0.15 else ("suspect" if ratio<0.25 else "healthy")
print("    %-14s chars=%-6d gzip_ratio=%.4f  %s"%(tag,len(t),ratio,verdict))
print("    %-14s cjk_punct_runs=%d  sample=%r"%(tag,len(runs),t[:110]))
PY
	kill "$pid" 2>/dev/null
	local w; for w in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 6
}

say "=== turboquant#241 cross-backend check: VULKAN/RADV on RDNA4 (same source+commit as the HIP arm) ==="
say "engine $(cd "$BIN/../.." && git log --oneline -1)"
# their exact failing pair first, then the isolation matrix
cell turbo4 turbo3      # <-- the reported failure
cell f16    f16         # control
cell turbo4 turbo4      # they report OK
cell turbo4 turbo2      # they report OK
cell turbo3 turbo3      # is it V-side only, or turbo3 anywhere?
cell f16    turbo3      # turbo3 V alone, K uncompressed
say "=== DONE ==="
