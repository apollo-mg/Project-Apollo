#!/usr/bin/env bash
# HA-20 with MTP on vs off: does speculative decoding change AGENT TASK OUTCOMES?
#
# WHY THIS LEG. MTP_STRUCTURED_OUTPUT.md found MTP's effect is class-dependent on this model:
#   tool calls (incl. computed args)  byte-stable, 12/12 correct in both arms
#   code                              changed on 3/6 tasks, broke 1 of those
#   prose                             3 variants / 6 draws
# HA-20 is dominated by tool-call work, so the prediction from that receipt is that MTP
# should be roughly harmless here. That is a real prediction and it deserves a real test --
# it is also the case where a null result is genuinely useful (it would mean MTP is a free
# 25% speedup for agent workloads specifically).
#
# ASYMMETRIC K, ON PURPOSE.
#   base  K=1  determinism verified on this model/build (6/6 byte-identical, MTP_DETERMINISM.md)
#   mtp   K=3  MTP is NONDETERMINISTIC at temp 0 -- 6 draws gave 4 distinct outputs. A single
#              MTP draw carries no information about the arm, exactly as with sampled arms in
#              HA20_SAMPLING_ARMS.md. Majority vote across 3.
#
# TOKEN-MATCHED TIMEOUTS, NOT WALL-MATCHED. Measured decode on this card at 64k f16:
#   base 79.5 t/s, mtp 99.7 t/s (+25%). Gemma's reference arm was 400 s at 59.34 t/s
#   = ~23.7k tokens. Matching that budget:
#     base 23736/79.5 = 299 s -> 300
#     mtp  23736/99.7 = 238 s -> 240
# Giving MTP an equal WALL clock would hand it 25% more tokens and let "MTP scores better"
# be a budget artifact. This campaign has already been bitten by exactly that: a
# finish_reason=length cap made MTP look more correct than base on toolcalc.
#
# Model is Qwen3.6-35B-A3B, NOT Ornith -- Ornith ships no nextn_predict_layers, so it has no
# MTP head to test. These are DIFFERENT MODELS (Qwen/Apache-2.0, 41 blocks vs
# deepreinforce-ai/MIT, 40 blocks), both on the qwen35moe arch; Ornith is NOT a fine-tune of
# Qwen3.6 -- that was my inference, corrected by Mark. Scores here are base-vs-mtp only;
# comparing them to Ornith's 14/20 compares two different models, not MTP.
set -u
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/35B-A3B/Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
RUNNER=scripts/run-scenarios.mjs          # stevibe's ORIGINAL, temp 0 default
MODEL_ID="Qwen3.6-35B-A3B-UD-IQ2_M"
KEY="sk-local-llamacpp-noauth"
PORT=${PORT:-8114}
OUT=/home/mark/projects/HermesAgent-20/ha20_mtp_ab
RECEIPTS=/mnt/TG_2TB/Projects/Apollo/data/receipts/battle16gb
SCEN=${SCEN:-$(seq -f "HA-%02g" 1 20)}
mkdir -p "$OUT"
LOG=$OUT/arm.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
export LD_LIBRARY_PATH="$BIN:${LD_LIBRARY_PATH:-}"
cd /home/mark/projects/HermesAgent-20

SRV=""
stop() {
	[ -n "$SRV" ] || return 0
	kill "$SRV" 2>/dev/null
	local w; for w in $(seq 1 40); do kill -0 "$SRV" 2>/dev/null || break; sleep 1; done
	kill -9 "$SRV" 2>/dev/null; SRV=""; sleep 6
}
trap stop EXIT

start_server() {
	local label=$1; shift
	local slog=$OUT/server_${label}.log
	setsid "$BIN/llama-server" -m "$MODEL" -c 65536 -b 1024 -ub 512 \
		-ctk f16 -ctv f16 -cb -fa on -np 1 -ngl 99 --cache-ram 0 \
		--port "$PORT" --host 0.0.0.0 --jinja "$@" \
		> "$slog" 2>&1 < /dev/null &
	SRV=$!
	local i
	for i in $(seq 1 240); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && {
			say "  $label server healthy pid=$SRV after $((i*2))s"; return 0; }
		kill -0 "$SRV" 2>/dev/null || { say "  $label SERVER DIED"; tail -20 "$slog" | tee -a "$LOG"; return 1; }
		sleep 2
	done
	say "  $label NEVER HEALTHY"; return 1
}

# Tool-calling smoke before each arm: a silent harness/template rejection presents as
# exit 0 / tool_events=0 and once cost this campaign 19 scenarios.
smoke() {
	local r; r=$(curl -s -m 120 "http://127.0.0.1:$PORT/v1/chat/completions" \
		-H 'Content-Type: application/json' -d '{"model":"q","temperature":0,"max_tokens":400,
		"messages":[{"role":"user","content":"What is the weather in Tokyo? Use the tool."}],
		"tools":[{"type":"function","function":{"name":"get_weather","description":"weather",
		"parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}]}' \
		| python3 -c "import sys,json; d=json.load(sys.stdin); c=d['choices'][0]; print(c.get('finish_reason'), bool(c['message'].get('tool_calls')))" 2>&1)
	say "  smoke: $r"
	echo "$r" | grep -q "tool_calls True" || { say "  ABORT: tool calling broken"; return 1; }
}

run_pass() {
	local label=$1 timeout_s=$2 tag=$3
	local sc
	for sc in $SCEN; do
		local f=$OUT/${tag}_${sc}.log
		local t0; t0=$(date +%s)
		timeout "$timeout_s" node "$RUNNER" --scenario "$sc" \
			--model "$MODEL_ID" --base-url "http://10.0.0.5:$PORT/v1" \
			--auth-mode bearer --api-key "$KEY" --json > "$f" 2>&1
		local rc=$?; local t1; t1=$(date +%s)
		local r; r=$(grep -m1 -E "^\[(PASS|FAIL|PARTIAL)\]" "$f")
		[ -z "$r" ] && r="[ERROR rc=$rc] $sc (no verdict — runaway or timeout)"
		local te; te=$(grep -oE "tool_events=[0-9]+" "$f" | tail -1)
		say "  $r  [$((t1-t0))s ${te:-tool_events=?}]"
	done
}

say "=== HA-20 MTP A/B on $MODEL_ID ==="

# ---- ARM A: base, K=1 ----
start_server base || exit 1
smoke || exit 1
say "--- ARM A: base, K=1, 300s/scenario ---"
run_pass base 300 base
stop

# ---- ARM B: MTP, K=3 ----
start_server mtp --spec-type draft-mtp --spec-draft-n-max 2 || exit 1
smoke || exit 1
for rep in 1 2 3; do
	say "--- ARM B: mtp, rep $rep/3, 240s/scenario ---"
	run_pass mtp 240 "mtp_r${rep}"
done
stop

say "=== COMPLETE ==="
grep -oE "draft acceptance = [0-9.]+" "$OUT/server_mtp.log" | tail -1 | sed 's/^/final /' | tee -a "$LOG"
