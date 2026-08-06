#!/usr/bin/env bash
# HA-20 on Ternary-Bonsai-27B Q2_g64 -- the agentic leg of "The Battle for 16GB".
#
# CELL BEING FILLED. Battle16GB scored Bonsai vs gemma-4-12B QAT on IFEval + GSM8K, on this
# same card. Bonsai won both. Neither suite measures multi-turn tool use, and gemma-4-12B now
# has an HA-20 number on this card (14/20 PASS, temp 0, K=1). This is Bonsai's.
#
# SAMPLING: temperature 0, the pack default and stevibe's UNMODIFIED runner. That is this
# campaign's own conclusion (HA20_SAMPLING_ARMS.md): recommended chat sampling bought nothing
# on agentic score and added a 15% per-scenario reproducibility floor. Note that Bonsai's GGUF
# ships general.sampling.{temp 1.0, top_k 20, top_p 0.95} -- chat defaults, overridden here.
#
# K=1 IS LEGITIMATE ON THIS BUILD: verified, not inherited. 3/3 byte-identical 1200-token
# greedy generations on the bonsai fork before this run (det_1..3, sha 2769dde8ac13d6b4).
# The earlier determinism receipt covered the turboquant fork only.
#
# TIMEOUT IS TOKEN-MATCHED, NOT WALL-MATCHED. Measured decode on this card, 64k f16 KV:
#   gemma  59.34 t/s (546 real HA-20 turns)
#   bonsai 46.02 t/s
# Gemma is ~29% faster per token, so an equal wall clock would silently hand Gemma a bigger
# token budget and let "Bonsai ran away more" be an artifact of the stopwatch. Arm B's ceiling
# was 400 s x 59.34 = ~23.7k tokens; matching that at 46.02 t/s needs 516 s. Rounded to 520.
#
# Scenarios run INDIVIDUALLY so one runaway cannot abort the batch -- that is exactly what
# killed the gemma arm A batch at HA-16.
set -u
cd /home/mark/projects/HermesAgent-20
RUNNER=scripts/run-scenarios.mjs          # stevibe's ORIGINAL, unmodified: temp 0 by default
MODEL="Ternary-Bonsai-27B-Q2_g64"
BASE="http://10.0.0.5:8099/v1"            # routable IP -- the Hermes agent runs inside docker
KEY="sk-local-llamacpp-noauth"
OUT=/home/mark/projects/HermesAgent-20/ha20_bonsai_t0
PER_SCENARIO_TIMEOUT=${PER_SCENARIO_TIMEOUT:-520}
SCEN=${SCEN:-$(seq -f "HA-%02g" 1 20)}
mkdir -p "$OUT"
LOG=$OUT/arm.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

curl -s -m 5 "${BASE%/v1}/health" | grep -q '"ok"' || { say "ABORT: bonsai server not healthy at $BASE"; exit 1; }
say "=== BONSAI-27B ternary, temp 0, K=1, per-scenario timeout ${PER_SCENARIO_TIMEOUT}s ==="

for SC in $SCEN; do
	f=$OUT/${SC}.log
	t0=$(date +%s)
	timeout "$PER_SCENARIO_TIMEOUT" node "$RUNNER" --scenario "$SC" \
		--model "$MODEL" --base-url "$BASE" \
		--auth-mode bearer --api-key "$KEY" --json > "$f" 2>&1
	rc=$?; t1=$(date +%s)
	r=$(grep -m1 -E "^\[(PASS|FAIL|PARTIAL)\]" "$f")
	[ -z "$r" ] && r="[ERROR rc=$rc] $SC (no verdict — runaway or timeout)"
	# tool_events distinguishes "model can't use tools" from "model used tools and failed";
	# a silent harness rejection shows as exit 0 with tool_events=0 (cost 19 scenarios once).
	te=$(grep -oE "tool_events=[0-9]+" "$f" | tail -1)
	say "  $r  [$((t1-t0))s ${te:-tool_events=?}]"
done
say "=== BONSAI ARM COMPLETE ==="
