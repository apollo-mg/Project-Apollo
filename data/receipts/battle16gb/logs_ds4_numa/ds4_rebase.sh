#!/usr/bin/env bash
# DS4 re-baseline at the corrected config, with the drift control the NUMA receipt lacked.
#
# WHY: every published DS4 figure on this fleet was measured under default first-touch NUMA
# placement, which DS4_NUMA_DISTRIBUTE.md showed costs ~22.7%. This run replaces the headline
# numbers. Two stated limits of that receipt are also fixed here:
#   - no repeat-control arm  -> arms run distribute -> none -> distribute (A/B/A)
#   - K=1 per policy         -> the whole load-and-measure cycle repeats, so run-to-run
#                               reproducibility is measured, not just within-arm spread
#
# WHAT GETS RECORDED (the previous receipts' other lesson: never one number without saying which)
#   - COLD  decode: draw 1 of a freshly loaded server on a dropped page cache = first-response
#   - WARM  decode: draws 6-9, after 4 discarded warming draws. Warming moves this config 2.7x
#                   and takes ~3 draws; "discard draw 1" was already shown to be insufficient.
#   - PREFILL: measured on a ~2000-token prompt. The 27-token prompt used previously makes
#              prompt-eval rate meaningless.
#   - length check: one 400-token draw while warm, to confirm decode is length-independent once
#              warming is complete (it was NOT before: 200-tok and 400-tok figures disagreed
#              purely because longer generations spend more of their life warm).
#   - gzip ratio as the degeneracy gate, and GPU clocks/power (fleet standard since 2026-07-17).
#
# CACHE DISCIPLINE: caches are dropped before EVERY arm including the no-NUMA control, because
# llama-server's own help warns that switching NUMA mode with a populated cache measures the old
# placement. All arms therefore start cold and equal.
set -u
exec 9>/home/mark/.ds4_rebase.lock
flock -n 9 || { echo "another ds4_rebase already running; exiting" >&2; exit 3; }

BIN=/home/mark/llama_tq_ds4/build_ds4/bin
MODEL=/home/mark/AI/Models/DS4-Flash/DeepSeek-V4-Flash-0731-UD-IQ1_S-00001-of-00003.gguf
OUT=/home/mark/ds4_rebase
rm -rf "$OUT"; mkdir -p "$OUT"
LOG=$OUT/rebase.log
PORT=8092
WARMUP=5      # draw 1 (cold) + 4 warming draws, all discarded from the WARM mean
MEASURE=4
GENTOK=200
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

# Build payloads in python to avoid shell-quoting a 2000-token prompt.
python3 - "$OUT" "$GENTOK" <<'PY'
import json, sys
out, gentok = sys.argv[1], int(sys.argv[2])
short = "Explain in three sentences why mixture-of-experts models are cheaper to run than dense models of the same parameter count."
# ~2000 tokens of ordinary prose, for a prefill measurement that isn't dominated by overhead.
para = ("The routing network selects a small subset of experts for each token, so the number of "
        "parameters actually multiplied per token is far smaller than the total parameter count. "
        "This decouples model capacity from per-token compute cost. ")
long = ("Read the following passage and then answer.\n\n" + para*90 +
        "\n\nQuestion: in one sentence, what does the passage claim about capacity and compute?")
def mk(prompt, maxtok):
    return {"model":"q","temperature":0,"max_tokens":maxtok,"cache_prompt":False,
            "messages":[{"role":"user","content":prompt}]}
json.dump(mk(short, gentok),  open(f"{out}/p_short.json","w"))
json.dump(mk(short, 400),     open(f"{out}/p_long400.json","w"))
json.dump(mk(long, 16),       open(f"{out}/p_prefill.json","w"))
PY

# $1 = arm tag, $2 = extra llama-server args
run_arm(){
	local tag=$1 extra=$2
	local slog=$OUT/server_${tag}.log
	say "########## ARM $tag  [${extra:-no numa flag}] ##########"
	if pgrep -x llama-server >/dev/null; then say "  ABORT: a server is already alive"; return 9; fi
	say "  dropping page cache"
	sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null 2>&1; sleep 5
	local t0 t1
	t0=$(date +%s)
	# shellcheck disable=SC2086
	LD_LIBRARY_PATH="$BIN" setsid "$BIN/llama-server" -m "$MODEL" \
		-c 8192 -ngl 99 -sm layer -ts 3,4,4,1 -fit off -fa on -ncmoe 40 \
		$extra -np 1 --host 127.0.0.1 --port "$PORT" --jinja > "$slog" 2>&1 < /dev/null &
	local pid=$! ok=0 i
	for i in $(seq 1 1200); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" != 1 ]; then
		say "  FAILED TO LOAD"; tail -6 "$slog" | sed 's/^/    | /' | tee -a "$LOG"
		kill -9 "$pid" 2>/dev/null; sleep 12; return 1
	fi
	t1=$(date +%s)
	say "  loaded in $((t1-t0))s  vram=[$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB' | tr '\n' ' ')]"
	say "  clocks=[$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader | tr '\n' ' ')] power=[$(nvidia-smi --query-gpu=power.draw --format=csv,noheader | tr '\n' ' ')]"

	local d
	for d in $(seq 1 $((WARMUP+MEASURE))); do
		curl -s -m 2400 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
			-d @"$OUT/p_short.json" > "$OUT/r_${tag}_d${d}.json" 2>/dev/null
	done
	say "  200-tok draws done; power under load=[$(nvidia-smi --query-gpu=power.draw --format=csv,noheader | tr '\n' ' ')]"
	curl -s -m 2400 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
		-d @"$OUT/p_long400.json" > "$OUT/r_${tag}_400.json" 2>/dev/null
	curl -s -m 2400 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
		-d @"$OUT/p_prefill.json" > "$OUT/r_${tag}_pref.json" 2>/dev/null

	python3 - "$slog" "$tag" "$GENTOK" "$WARMUP" "$OUT" <<'PY' | tee -a "$LOG"
import sys, json, gzip, os, statistics, re
slog, tag, gentok, warm, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
# Parse line-by-line: the regex "eval time =" also matches "prompt eval time =", which silently
# interleaved prefill and decode rows in an earlier run and produced meaningless numbers.
dec, pre = [], []
row = re.compile(r"eval time =\s*[\d.]+ ms /\s*(\d+) tokens \(\s*([\d.]+) ms per token,\s*([\d.]+) tokens per second")
for line in open(slog, errors='replace'):
    m = row.search(line)
    if not m: continue
    n, mspt, tps = int(m.group(1)), float(m.group(2)), float(m.group(3))
    (pre if "prompt eval time" in line else dec).append((n, mspt, tps))
d200 = [t for n,_,t in dec if n == gentok]
cold  = d200[0] if d200 else None
meas  = d200[warm:warm+4]
d400  = [t for n,_,t in dec if n == 400]
prefill = [(n,mspt,tps) for n,mspt,tps in pre if n > 500]
gz=set()
for f in os.listdir(out):
    if f.startswith(f"r_{tag}_d") and f.endswith(".json"):
        try:
            m=json.load(open(f"{out}/{f}"))["choices"][0]["message"]
            s=(m.get("content") or "")+(m.get("reasoning_content") or "")
            if s.strip(): gz.add(round(len(gzip.compress(s.encode(),6))/len(s.encode()),4))
        except Exception: pass
print(f"    {tag:<12} COLD(draw1) = {cold if cold else 'n/a'} t/s")
print(f"    {tag:<12} warming     = {[round(x,2) for x in d200[1:warm]]}")
if meas:
    mean=statistics.mean(meas); spread=100*(max(meas)-min(meas))/max(mean,1e-9)
    flag="OK" if spread<=8 else "*** UNSTABLE — warming incomplete ***"
    print(f"    {tag:<12} WARM        = {[round(x,2) for x in meas]}  mean={mean:.2f} t/s  spread={spread:.1f}% {flag}")
else:
    print(f"    {tag:<12} WARM        = NO MEASURED DRAWS")
print(f"    {tag:<12} 400-tok warm= {[round(x,2) for x in d400]} t/s  (length-independence check)")
if prefill:
    n,mspt,tps = prefill[-1]
    print(f"    {tag:<12} PREFILL     = {tps:.1f} tok/s ({mspt:.1f} ms/tok) on {n} tokens")
else:
    print(f"    {tag:<12} PREFILL     = not captured")
print(f"    {tag:<12} gzip        = {sorted(gz)}")
PY
	kill "$pid" 2>/dev/null
	local w; for w in $(seq 1 90); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 15
	return 0
}

say "===== DS4 RE-BASELINE @ corrected config (--numa distribute) ====="
say "prior published: 2.16 t/s (cold, bad NUMA) / 4.71-4.75 warm (bad NUMA) / 5.62 (distribute, K=1)"
say "arms: distribute -> none -> distribute. Middle arm is the control; A vs A' is the drift check."
run_arm "dist_a" "--numa distribute" || say "  dist_a failed"
run_arm "nonuma" ""                  || say "  nonuma failed"
run_arm "dist_b" "--numa distribute" || say "  dist_b failed"
say "===== DONE ====="
say "READ: (1) |dist_a - dist_b| must be < |nonuma - dist_*| or the instrument can't resolve it."
say "      (2) any arm UNSTABLE (>8% spread) -> do not average that arm."
