#!/usr/bin/env bash
# Serving stack for the HermesAgent-20 agentic leg of "The Battle for 16GB".
#
# WHY. Battle16GB (2026-07-18) scored Ternary-Bonsai-27B Q2_g64 (1.71 bpw) vs
# gemma-4-12B-it QAT Q4_K_XL (~4.3 bpw) on IFEval + GSM8K. Bonsai won both, decisively.
# Neither suite measures multi-turn tool use. HA-20 does, and gemma-4-12B has now been
# measured on it on this exact card (14/20 PASS, temp 0, K=1 -- HA20_SAMPLING_ARMS.md).
# This is the matching Bonsai cell.
#
# KV GEOMETRY (measured from GGUF metadata, not assumed):
#   block_count 64, head_count_kv 4, key_length 256, value_length 256
#   qwen35.full_attention_interval = 4   <-- HYBRID. Only 16 of 64 layers hold a growing KV.
#   The other 48 are SSM (ssm.state_size 128, ssm.inner_size 6144, ssm.conv_kernel 4):
#   constant state, does NOT grow with context.
#   => 16 attn layers x 4 kv heads x (256+256) x 2 B = 64 KiB/token at f16
#   => 64k ctx = 4.0 GiB KV.  + 7.06 GiB weights = ~11.1 GiB.  Fits 16 GB with f16 KV.
# Treating all 64 layers as attention gives 16.00 GiB and the wrong conclusion that Bonsai
# needs quantised KV here. It does not -- so this leg carries NO KV-codec confound against
# the gemma f16 leg.
#
# SERVING PARITY with start_gemma_bench.sh -- identical except model, engine and port:
#   -c 65536       Hermes hard-fails below 64,000 ctx (agent_exit_code=1)
#   f16 KV         no codec in the loop, same as the gemma leg
#   -np 1          single slot; no slot-order asymmetry
#   --cache-ram 0  prompt cache off
#   -fa on -ngl 99
# NO --top-k: the arms comparison concluded benchmark at temperature 0, where top_k is
# inert. Note the GGUF ships general.sampling.{temp 1.0, top_k 20, top_p 0.95} as the
# model's recommended CHAT sampling; the harness sends temperature 0 explicitly.
#
# ENGINE. Must be the bonsai fork (10068 + PR #25707 q2_0 CUDA/HIP kernels, branch
# bonsai-rdna4). The turboquant fork used for gemma has no q2_0 ternary kernels.
set -u
SERVER=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_bonsai/build_hip/bin/llama-server
MODEL="/mnt/TG_2TB/AI/Models/Bonsai/Ternary-Bonsai-27B-Q2_g64.gguf"
PORT=${PORT:-8099}
CTK=${CTK:-f16}
CTV=${CTV:-f16}
LOG=/home/mark/projects/HermesAgent-20/bonsai_bench_server.log
RECEIPTS=/mnt/TG_2TB/Projects/Apollo/data/receipts/battle16gb
[ -s "$MODEL" ] || { echo "FATAL: model missing at $MODEL"; exit 1; }
[ -x "$SERVER" ] || { echo "FATAL: bonsai llama-server missing at $SERVER"; exit 1; }
export LD_LIBRARY_PATH="$(dirname "$SERVER"):${LD_LIBRARY_PATH:-}"
ss -ltn 2>/dev/null | grep -q ":$PORT " && { echo "ABORT: port $PORT busy"; exit 1; }
mkdir -p "$RECEIPTS"

# Serving config is written to data/receipts AT LAUNCH, not after. The original Battle16GB
# per-leg serving configs lived in the /tmp scratchpad and were destroyed by a reboot.
CFG=$RECEIPTS/serving_config_bonsai_ha20.txt
{
	echo "date              $(date -Is)"
	echo "host              $(hostname) 10.0.0.5  RX 9070 XT gfx1201 16 GB"
	echo "engine            $SERVER"
	echo "engine_git        $(cd "$(dirname "$SERVER")/../.." && git log --oneline -1 2>/dev/null)"
	echo "engine_branch     $(cd "$(dirname "$SERVER")/../.." && git rev-parse --abbrev-ref HEAD 2>/dev/null)"
	echo "model             $MODEL"
	echo "model_bytes       $(stat -c%s "$MODEL")"
	echo "model_sha256      (see sha file)"
	echo "ctx               65536"
	echo "kv                -ctk $CTK -ctv $CTV"
	echo "sampling          temperature 0 (harness-sent); no server-side top_k/top_p override"
	echo "flags             -c 65536 -b 1024 -ub 512 -cb -fa on -np 1 -ngl 99 --cache-ram 0 --jinja"
	rocm-smi --showclocks --showpower 2>/dev/null | grep -E "sclk|mclk|Power" | sed 's/^/clock             /'
} > "$CFG"

echo "=== $(date -Is) bonsai-27B ternary HA-20 bench server (ctk=$CTK ctv=$CTV) ===" >> "$LOG"
setsid "$SERVER" -m "$MODEL" -c 65536 -b 1024 -ub 512 \
	-ctk "$CTK" -ctv "$CTV" -cb -fa on -np 1 -ngl 99 --cache-ram 0 \
	--port "$PORT" --host 0.0.0.0 --jinja \
	>> "$LOG" 2>&1 < /dev/null &
PID=$!; echo "$PID" > /home/mark/projects/HermesAgent-20/bonsai_bench.pid
for i in $(seq 1 240); do
	curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && {
		echo "HEALTHY pid=$PID port=$PORT after ${i}s"
		VRAM=$(rocm-smi --showmeminfo vram 2>/dev/null | grep -i "Used" | grep -oE '[0-9]+')
		echo "vram_used_bytes   $VRAM" | tee -a "$CFG"
		grep -iE "KV self|kv cache|memory breakdown|compute buffer|n_ctx_seq" "$LOG" | tail -12
		exit 0; }
	kill -0 "$PID" 2>/dev/null || { echo "DIED after ${i}s"; tail -25 "$LOG"; exit 1; }
	sleep 2
done
echo "NEVER HEALTHY"; exit 1
