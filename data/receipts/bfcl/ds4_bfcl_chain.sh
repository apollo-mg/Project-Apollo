#!/usr/bin/env bash
# DS4-Flash on the BFCL parallel categories — the matched follow-up to leg W3.
#
# THE QUESTION: leg W3 found Puzzle-75B-A9B-UD-IQ4-XL scores 3/35 = 8.6% on `parallel` and
# 8.6% on `parallel_multiple`, while tying Qwen3.6-27B-Q8 on `multiple` (88.6% both). The ENTIRE
# 30pp overall gap is the parallel family; 32/35 failures are wrong_count -- Puzzle emits one
# call where N are required. Explicitly NOT a token-budget artifact (failing items produced
# 70-416 tokens, median 162).
#
# DS4-Flash is 284B at 2.32 bpw -- LOWER precision than Puzzle's IQ4 -- so if it handles parallel
# calls correctly, "low bits break schema handling" fails as a general explanation and the finger
# points at Puzzle specifically. If it also collapses, the boundary looks structural.
#
# WHAT THIS DOES *NOT* ANSWER: the receipt's open question, "is Puzzle's collapse a QUANT effect
# or architectural?" That needs a higher-quant *Puzzle* control (the APEX i-quality tier at
# 5.30 bpw is the candidate). DS4 is a different model and speaks to neither half.
#
# HARNESS VERSION -- the trap this script exists to avoid. The published leg ran in ~/bfcl_venv
# with bfcl-eval **2026.3.23** (confirmed in ~/bfcl_install.log, venv created 2026-07-21 15:41).
# That venv's site-packages are now gone. The surviving ~/bfcl_eval_venv holds **2025.8.6.2** --
# an OLDER pin created two days later. Running DS4 there would score against different test data
# and a different scorer while calling itself "matched". So this builds a fresh venv pinned to
# 2026.3.23.
set -u
exec 9>/home/mark/.ds4_bfcl.lock
flock -n 9 || { echo "already running"; exit 3; }

VENV=/home/mark/bfcl_w3_venv
OUT=/home/mark/ds4_bfcl
BIN=/home/mark/llama_tq_ds4/build_ds4/bin
MODEL=/home/mark/AI/Models/DS4-Flash/DeepSeek-V4-Flash-0731-UD-IQ1_S-00001-of-00003.gguf
PORT=8091
MODELID="apollo/ds4-flash-iq1s"
mkdir -p "$OUT"
LOG=$OUT/bfcl.log
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

# ---- 1. matched harness ---------------------------------------------------------------------
if [ ! -x "$VENV/bin/bfcl" ]; then
	say "creating venv pinned to bfcl-eval==2026.3.23"
	python3 -m venv "$VENV" >/dev/null 2>&1 || { say "venv creation failed"; exit 1; }
	"$VENV/bin/pip" -q install "bfcl-eval==2026.3.23" > "$OUT/pip.log" 2>&1 || {
		say "PIN INSTALL FAILED — refusing to fall back to another version:"; tail -5 "$OUT/pip.log" | sed 's/^/    /' | tee -a "$LOG"; exit 1; }
fi
V=$("$VENV/bin/pip" show bfcl-eval 2>/dev/null | awk '/^Version:/{print $2}')
say "harness version: $V"
[ "$V" = "2026.3.23" ] || { say "ABORT: harness is $V, leg W3 used 2026.3.23 — not a matched comparison"; exit 1; }

# ---- 2. register the model (mirrors the live Puzzle entry exactly) ---------------------------
PKG=$("$VENV/bin/python" -c "import os,bfcl_eval;print(os.path.dirname(bfcl_eval.__file__))")
CFG="$PKG/constants/model_config.py"
if ! grep -q "$MODELID" "$CFG"; then
	say "registering $MODELID in model_config.py"
	cat >> "$CFG" <<EOF

MODEL_CONFIG_MAPPING['$MODELID'] = ModelConfig(
    model_name='$MODELID',
    display_name='Apollo DS4-Flash',
    url='local',
    org='Apollo',
    license='None',
    model_handler=OpenAICompletionsHandler
)
EOF
fi

# ---- 3. restrict to the SAME items leg W3 used ----------------------------------------------
# Reuse subset_ids_used.json rather than re-running build_bfcl_subset.py's RNG: identical items
# are guaranteed even if the packaged dataset changed between versions.
#
# WRITING THIS FILE IS NOT ENOUGH. `bfcl generate` ignores it unless --run-ids is passed (it
# defaults False), and `evaluate` has no --run-ids at all -- it needs --partial-eval or it raises
# on the entries generate skipped. The 2026-08-03 run wrote the subset, omitted both flags, and
# silently ran the FULL 200/category: 400 items, ~85 h, and a score that looked plausible
# (51.5%/17.0%) but was scored against total_count=200 and so was not comparable to leg W3's 35.
# Step 6 now asserts the denominator rather than trusting the flags stayed correct.
"$VENV/bin/python" - "$OUT" <<'PY' | tee -a "$LOG"
import json, os, sys, bfcl_eval
from bfcl_eval.constants.eval_config import TEST_IDS_TO_GENERATE_PATH
out = sys.argv[1]
saved = json.load(open("/home/mark/subset_ids_used.json"))
example = os.path.join(os.path.dirname(bfcl_eval.__file__), "test_case_ids_to_generate.json.example")
skel = json.load(open(example))
for k in skel: skel[k] = []
kept = {}
for cat in ("parallel", "parallel_multiple"):
    ids = saved.get(cat, [])
    skel[cat] = ids
    kept[cat] = len(ids)
json.dump(skel, open(TEST_IDS_TO_GENERATE_PATH, "w"), indent=2)
# the contract step 6 verifies
json.dump(kept, open(os.path.join(out, "expected_counts.json"), "w"), indent=2)
print("    subset written:", kept, "->", TEST_IDS_TO_GENERATE_PATH)
PY
[ -s "$OUT/expected_counts.json" ] || { say "ABORT: subset step wrote no expected_counts.json"; exit 1; }

# ---- 4. serve DS4 ----------------------------------------------------------------------------
if pgrep -x llama-server >/dev/null; then say "ABORT: a server is already alive"; exit 9; fi
say "starting DS4 (-c 16384, --numa distribute)"
LD_LIBRARY_PATH="$BIN" setsid "$BIN/llama-server" -m "$MODEL" \
	-c 16384 -ngl 99 -sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40 \
	--numa distribute -np 1 --host 0.0.0.0 --port "$PORT" --jinja \
	> "$OUT/server.log" 2>&1 < /dev/null &
PID=$!
ok=0
for i in $(seq 1 1200); do
	curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
	kill -0 "$PID" 2>/dev/null || break
	sleep 2
done
[ "$ok" = 1 ] || { say "FAILED TO LOAD"; tail -6 "$OUT/server.log" | sed 's/^/  | /' | tee -a "$LOG"; exit 1; }
say "loaded. warming (cold is ~1.13 t/s vs ~5.2 warm under --numa distribute)"
for d in 1 2 3 4; do
	curl -s -m 2400 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
		-d '{"model":"q","temperature":0,"max_tokens":200,"cache_prompt":false,"messages":[{"role":"user","content":"Say hello."}]}' >/dev/null 2>&1
done

# ---- 5. generate + evaluate ------------------------------------------------------------------
export OPENAI_BASE_URL="http://127.0.0.1:$PORT/v1"
export OPENAI_API_KEY="none"
say "generate (70 items, temp 0, --run-ids) — BFCL prompts carry full tool schemas, so prefill-bound"
( cd "$VENV" && "$VENV/bin/bfcl" generate --model "$MODELID" --test-category parallel,parallel_multiple \
	--num-threads 1 --temperature 0 --run-ids ) >> "$OUT/generate.log" 2>&1
GRC=$?
say "generate rc=$GRC"
# A failed generate makes everything downstream meaningless. The 2026-08-03 attempt returned rc=1,
# evaluated anyway, and still printed "===== DONE =====".
[ "$GRC" = 0 ] || { say "ABORT: generate failed (rc=$GRC) — not evaluating a partial run"
	tail -8 "$OUT/generate.log" | sed 's/^/  | /' | tee -a "$LOG"; kill "$PID" 2>/dev/null; exit 1; }

# --partial-eval: generate produced only the subset, so the scorer must not raise on the
# entries it deliberately skipped. There is no --run-ids on `evaluate`.
( cd "$VENV" && "$VENV/bin/bfcl" evaluate --model "$MODELID" --test-category parallel,parallel_multiple \
	--partial-eval ) > "$OUT/evaluate.log" 2>&1
ERC=$?
say "evaluate rc=$ERC"
[ "$ERC" = 0 ] || { say "ABORT: evaluate failed (rc=$ERC)"
	tail -8 "$OUT/evaluate.log" | sed 's/^/  | /' | tee -a "$LOG"; kill "$PID" 2>/dev/null; exit 1; }
grep -E "Accuracy|Test completed|Model:" "$OUT/evaluate.log" | tail -8 | sed 's/^/    /' | tee -a "$LOG"

# ---- 6. ASSERT THE DENOMINATOR ---------------------------------------------------------------
# The failure this guards against is silent and expensive: a score against the wrong item set is
# still a well-formed number. Compare each category's total_count to the subset actually requested
# and refuse to call the run comparable if they disagree.
SCORE_DIR="$PKG/../score/$(echo "$MODELID" | tr '/' '_')/non_live"
"$VENV/bin/python" - "$OUT" "$SCORE_DIR" <<'PY' | tee -a "$LOG"
import json, os, sys
out, score_dir = sys.argv[1], sys.argv[2]
expected = json.load(open(os.path.join(out, "expected_counts.json")))
bad = []
for cat, want in expected.items():
    p = os.path.join(score_dir, f"BFCL_v4_{cat}_score.json")
    if not os.path.isfile(p):
        bad.append(f"{cat}: no score file at {p}"); continue
    with open(p) as f:
        s = json.loads(f.readline())
    got = s.get("total_count")
    tag = "OK " if got == want else "BAD"
    print(f"    [{tag}] {cat}: total_count={got} expected={want} "
          f"accuracy={s.get('accuracy')} correct={s.get('correct_count')}")
    if got != want:
        bad.append(f"{cat}: scored {got} items, subset requested {want}")
if bad:
    print("\n    *** DENOMINATOR MISMATCH — THIS RUN IS NOT COMPARABLE TO LEG W3 ***")
    for b in bad: print("      -", b)
    print("    Cause is almost always a missing --run-ids on generate.")
    sys.exit(1)
print("    denominator check passed — matched to the leg W3 subset")
PY
[ "${PIPESTATUS[0]}" = 0 ] || { say "ABORT: denominator check failed"; kill "$PID" 2>/dev/null; exit 1; }

# ---- 7. teardown -----------------------------------------------------------------------------
kill "$PID" 2>/dev/null
for w in $(seq 1 90); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
kill -9 "$PID" 2>/dev/null
say "===== DONE ====="
say "READ: leg W3 reference — Puzzle 8.6%/8.6%, Qwen 91.4%/80.0% on parallel/parallel_multiple."
say "READ: DS4-Flash IQ1_S matched result — 48.6%/20.0% (parallel/parallel_multiple), 34.3% family."
