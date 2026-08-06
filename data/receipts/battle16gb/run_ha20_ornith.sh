#!/usr/bin/env bash
# HA-20 on Ornith-1.0-35B-A3B IQ2_M -- third contender in "The Battle for 16GB".
#
# WHY A THIRD MODEL. Gemma-4-12B QAT (dense, ~4.3 bpw) scored 14/20 and Ternary-Bonsai-27B
# (hybrid SSM, 1.71 bpw) scored 15/20 -- one scenario apart, inside this benchmark's own
# 15% noise floor. Ornith is a third architecture (qwen35moe, 256 experts / 8 active, ~2.5
# bpw). Mark's hypothesis under test: these scenarios may be too easy to discriminate.
# 9 of 20 have never failed across 5 prior model-observations; only HA-07 and HA-17 have
# defeated every model. See PREDICTIONS_ha20_ornith.md (sealed before this run).
#
# SAMPLING: temperature 0, stevibe's runner UNMODIFIED -- this campaign's own conclusion
# (HA20_SAMPLING_ARMS.md). K=1 verified legitimate on THIS build: 3/3 byte-identical
# 1200-token greedy generations, sha 7c5bac70bae09cd2.
#
# TIMEOUT IS TOKEN-MATCHED, NOT WALL-MATCHED, and here that means a SHORTER wall clock.
# Measured decode, 64k f16 KV: ornith 77.13 t/s, gemma 59.34 t/s, bonsai 46.02 t/s.
# Ornith is the FASTEST of the three, so an equal wall clock would hand it a bigger token
# budget than the gemma reference arm got. 400 s x 59.34 / 77.13 = 308 s -> 310 s.
set -u
cd /home/mark/projects/HermesAgent-20
RUNNER=scripts/run-scenarios.mjs          # stevibe's ORIGINAL: temp 0 by default
MODEL="Ornith-1.0-35B-UD-IQ2_M"
BASE="http://10.0.0.5:8100/v1"            # routable IP -- Hermes agent runs inside docker
KEY="sk-local-llamacpp-noauth"
OUT=/home/mark/projects/HermesAgent-20/ha20_ornith_t0
PER_SCENARIO_TIMEOUT=${PER_SCENARIO_TIMEOUT:-310}
SCEN=${SCEN:-$(seq -f "HA-%02g" 1 20)}
mkdir -p "$OUT"
LOG=$OUT/arm.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

curl -s -m 5 "${BASE%/v1}/health" | grep -q '"ok"' || { say "ABORT: ornith server not healthy at $BASE"; exit 1; }
say "=== ORNITH-35B-A3B IQ2_M, temp 0, K=1, per-scenario timeout ${PER_SCENARIO_TIMEOUT}s ==="

for SC in $SCEN; do
	f=$OUT/${SC}.log
	t0=$(date +%s)
	timeout "$PER_SCENARIO_TIMEOUT" node "$RUNNER" --scenario "$SC" \
		--model "$MODEL" --base-url "$BASE" \
		--auth-mode bearer --api-key "$KEY" --json > "$f" 2>&1
	rc=$?; t1=$(date +%s)
	r=$(grep -m1 -E "^\[(PASS|FAIL|PARTIAL)\]" "$f")
	[ -z "$r" ] && r="[ERROR rc=$rc] $SC (no verdict — runaway or timeout)"
	# tool_events separates "can't use tools" from "used tools and failed"; a silent harness
	# rejection shows as exit 0 with tool_events=0 and once cost 19 scenarios.
	te=$(grep -oE "tool_events=[0-9]+" "$f" | tail -1)
	say "  $r  [$((t1-t0))s ${te:-tool_events=?}]"
done
say "=== ORNITH ARM COMPLETE ==="
