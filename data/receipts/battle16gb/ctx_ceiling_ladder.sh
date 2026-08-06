#!/usr/bin/env bash
# How much context can each "Battle for 16GB" contender actually serve on the 16 GB card?
#
# THE CLAIM UNDER TEST. Both models advertise a 262,144-token window
# (gemma4.context_length = qwen35.context_length = 262144). Their KV geometries are opposite:
#
#   gemma-4-12B   48 layers, 5:1 SWA. 8 global layers x 1 kv head x (512+512) x 2 B
#                 = 16 KiB/token growing, + ~0.31 GiB constant for the 1024-token SWA window.
#   bonsai-27B    64 layers, full_attention_interval 4. 16 global layers x 4 kv heads
#                 x (256+256) x 2 B = 64 KiB/token growing, + constant SSM state.
#
# So the 27B's context costs 4x the 12B's per token. Arithmetic says gemma reaches 262k
# (4.0 GiB KV) and bonsai cannot (16.0 GiB KV, larger than the whole card).
# ARITHMETIC IS NOT A RECEIPT -- the same closed form, applied to all 64 bonsai layers
# instead of the 16 attention layers, said bonsai could not even serve 64k. It serves it fine.
# So: measure. Load, read VRAM, unload.
set -u
OUT=/mnt/TG_2TB/Projects/Apollo/data/receipts/battle16gb
TSV=$OUT/ctx_ceiling.tsv
LOG=$OUT/ctx_ceiling.log
mkdir -p "$OUT"
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
[ -s "$TSV" ] || printf 'model\tctx\tkv\tstatus\tvram_used_B\tserver_B\tload_s\n' > "$TSV"

BONSAI_BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_bonsai/build_hip/bin
TQ_BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin
BONSAI_M="/mnt/TG_2TB/AI/Models/Bonsai/Ternary-Bonsai-27B-Q2_g64.gguf"
GEMMA_M="/mnt/TG_2TB/AI/Models/Gemma 4/12B/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"
PORT=8101

vram() { rocm-smi --showmeminfo vram 2>/dev/null | grep -i "Used" | grep -oE '[0-9]{6,}' | head -1; }

probe() {
	local tag=$1 bin=$2 model=$3 ctx=$4
	local slog=/tmp/ctxladder_${tag}_${ctx}.log
	local idle; idle=$(vram)
	local t0; t0=$(date +%s)
	LD_LIBRARY_PATH="$bin" setsid "$bin/llama-server" -m "$model" -c "$ctx" \
		-b 512 -ub 512 -ctk f16 -ctv f16 -fa on -np 1 -ngl 99 --cache-ram 0 \
		--port "$PORT" --host 127.0.0.1 > "$slog" 2>&1 < /dev/null &
	local pid=$!
	local st=TIMEOUT used=0
	for i in $(seq 1 150); do
		if curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"'; then
			st=OK; used=$(vram); break
		fi
		kill -0 "$pid" 2>/dev/null || { st=DIED; break; }
		sleep 2
	done
	local t1; t1=$(date +%s)
	local srv=0; [ "$st" = OK ] && srv=$(( used - idle ))
	printf '%s\t%s\tf16\t%s\t%s\t%s\t%s\n' "$tag" "$ctx" "$st" "${used:-0}" "$srv" "$((t1-t0))" >> "$TSV"
	if [ "$st" = OK ]; then
		say "  $tag ctx=$ctx  OK   server=$(awk -v b="$srv" 'BEGIN{printf "%.2f", b/1073741824}') GiB  ($((t1-t0))s)"
	else
		say "  $tag ctx=$ctx  $st"
		grep -iE "error|failed|alloc|out of memory|ggml_backend" "$slog" | tail -3 | sed 's/^/      /' | tee -a "$LOG"
	fi
	kill "$pid" 2>/dev/null
	for i in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 5
}

pgrep -f "llama-server" >/dev/null && { say "ABORT: a llama-server is still running"; exit 1; }
say "=== context ceiling ladder, f16 KV, 16 GB RX 9070 XT (desktop running) ==="
for c in 32768 65536; do probe bonsai "$BONSAI_BIN" "$BONSAI_M" "$c"; done
for c in 32768 65536; do probe gemma "$TQ_BIN" "$GEMMA_M" "$c"; done
say "=== LADDER COMPLETE ==="
column -t -s"$(printf '\t')" "$TSV" | tee -a "$LOG"
