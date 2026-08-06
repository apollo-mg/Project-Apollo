#!/usr/bin/env bash
# Serving stack for the Ornith-35B-A3B leg of "The Battle for 16GB" (HermesAgent-20).
#
# THIRD CONTENDER. Gemma-4-12B QAT (~4.3 bpw, dense) 14/20 and Ternary-Bonsai-27B (1.71 bpw,
# hybrid SSM) 15/20 landed one scenario apart. Ornith is a third architecture entirely:
# qwen35moe, 256 experts / 8 active (~3B active params), IQ2_M ~2.5 bpw, 10.77 GiB.
#
# KV GEOMETRY (from GGUF metadata):
#   block_count 40, full_attention_interval 4 -> 10 growing-KV layers
#   head_count_kv 2, key_length 256, value_length 256
#   => 10 x 2 x (256+256) x 2 B = 20 KiB/token at f16 -> 1.25 GiB at 64k
#   The other 30 layers are SSM (ssm.state_size 128, ssm.inner_size 4096): constant state.
# That is ~3.2x cheaper per token than Bonsai (64.5 KiB measured) despite Ornith being the
# LARGEST model of the three. Sparsity and KV cost are independent axes.
#
# MEASURED at first load, -c 65536 f16 KV: 12.17 GiB server footprint, 77.13 t/s decode --
# fastest of the three legs (gemma 59.34, bonsai 46.02).
#
# SERVING PARITY with start_gemma_bench.sh / start_bonsai_bench.sh -- identical flags, and
# the SAME ENGINE as the gemma leg (turboquant), which removes the cross-fork caveat that
# applies to the bonsai comparison.
#   -c 65536       Hermes hard-fails below 64,000 ctx (agent_exit_code=1)
#   f16 KV, -np 1, --cache-ram 0, -fa on, -ngl 99
# No server-side top_k: the harness sends temperature 0, where top_k is inert. The GGUF ships
# general.sampling.{temp 1.0, top_k 20, top_p 0.95} as CHAT defaults -- not used here.
set -u
SERVER=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin/llama-server
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/35B-A3B/Ornith-1.0-35B-UD-IQ2_M.gguf"
PORT=${PORT:-8100}
CTX=${CTX:-65536}
LOG=/home/mark/projects/HermesAgent-20/ornith_bench_server.log
RECEIPTS=/mnt/TG_2TB/Projects/Apollo/data/receipts/battle16gb
[ -s "$MODEL" ] || { echo "FATAL: model missing at $MODEL"; exit 1; }
[ -x "$SERVER" ] || { echo "FATAL: llama-server missing at $SERVER"; exit 1; }
export LD_LIBRARY_PATH="$(dirname "$SERVER"):${LD_LIBRARY_PATH:-}"
ss -ltn 2>/dev/null | grep -q ":$PORT " && { echo "ABORT: port $PORT busy"; exit 1; }
mkdir -p "$RECEIPTS"

IDLE=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -i "Used" | grep -oE '[0-9]{6,}' | head -1)
CFG=$RECEIPTS/serving_config_ornith_ha20.txt
{
	echo "date              $(date -Is)"
	echo "host              $(hostname) 10.0.0.5  RX 9070 XT gfx1201 16 GB"
	echo "engine            $SERVER"
	echo "engine_git        $(cd "$(dirname "$SERVER")/../.." && git log --oneline -1 2>/dev/null)"
	echo "model             $MODEL"
	echo "model_bytes       $(stat -c%s "$MODEL")"
	echo "ctx               $CTX"
	echo "kv                -ctk f16 -ctv f16"
	echo "sampling          temperature 0 (harness-sent); no server-side override"
	echo "flags             -c $CTX -b 1024 -ub 512 -cb -fa on -np 1 -ngl 99 --cache-ram 0 --jinja"
	echo "vram_idle_bytes   ${IDLE:-unknown}"
	rocm-smi --showclocks --showpower 2>/dev/null | grep -E "sclk|mclk|Power \(W\)" | sed 's/^/clock             /'
} > "$CFG"

echo "=== $(date -Is) ornith-35B-A3B MoE HA-20 bench server (ctx=$CTX) ===" >> "$LOG"
setsid "$SERVER" -m "$MODEL" -c "$CTX" -b 1024 -ub 512 \
	-ctk f16 -ctv f16 -cb -fa on -np 1 -ngl 99 --cache-ram 0 \
	--port "$PORT" --host 0.0.0.0 --jinja \
	>> "$LOG" 2>&1 < /dev/null &
PID=$!; echo "$PID" > /home/mark/projects/HermesAgent-20/ornith_bench.pid
for i in $(seq 1 240); do
	curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && {
		USED=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -i "Used" | grep -oE '[0-9]{6,}' | head -1)
		echo "HEALTHY pid=$PID port=$PORT after $((i*2))s"
		echo "vram_used_bytes   $USED  (server $(awk -v a="$USED" -v b="${IDLE:-0}" 'BEGIN{printf "%.2f", (a-b)/1073741824}') GiB)" | tee -a "$CFG"
		exit 0; }
	kill -0 "$PID" 2>/dev/null || { echo "DIED after $((i*2))s"; tail -25 "$LOG"; exit 1; }
	sleep 2
done
echo "NEVER HEALTHY"; exit 1
