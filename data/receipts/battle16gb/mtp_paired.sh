#!/usr/bin/env bash
# Is MTP's output difference attributable to MTP -- or just to restarting the server?
#
# WHAT WENT WRONG THE FIRST TIME. mtp_ab.sh compared ONE base instance against ONE mtp
# instance and found a divergence at char 126, which I attributed to speculative decoding.
# That attribution was invalid: a third base instance, same flags, showed base output is not
# stable across restarts either.
#     instance 1 (port 8106): 6480076f296971b3  4770 chars
#     instance 2 (port 8108): 5f3fef54edff5279  4865 chars
#     instance 3 (port 8109): 5f3fef54edff5279  4865 chars   (2 draws, both)
# Within a single server instance every arm is 3/3 byte-identical. Across restarts, base
# disagrees with itself. So a single base-vs-mtp diff cannot separate "MTP changed the
# output" from "the server restarted".
#
# PAIRED DESIGN. Alternate base/mtp across N restarts each, same prompt, temp 0.
#   - If base is stable across its restarts and mtp is stable across its restarts, and the
#     two clusters differ  -> the difference IS attributable to MTP.
#   - If base disagrees with ITSELF as often as it disagrees with mtp -> restart noise
#     dominates and the A/B cannot resolve MTP's effect at this sample size.
# Alternating (not blocked) so any slow drift in machine state hits both arms equally.
set -u
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/35B-A3B/Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
OUT=/home/mark/projects/HermesAgent-20/mtp_paired
PROBE=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/detprobe.json
PORT=${PORT:-8110}
REPS=${REPS:-3}
mkdir -p "$OUT"
LOG=$OUT/paired.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
export LD_LIBRARY_PATH="$BIN:${LD_LIBRARY_PATH:-}"

run_once() {
	local label=$1 rep=$2; shift 2
	local slog=$OUT/server_${label}_${rep}.log
	setsid "$BIN/llama-server" -m "$MODEL" -c 65536 -b 1024 -ub 512 \
		-ctk f16 -ctv f16 -cb -fa on -np 1 -ngl 99 --cache-ram 0 \
		--port "$PORT" --host 127.0.0.1 --jinja "$@" \
		> "$slog" 2>&1 < /dev/null &
	local pid=$!
	local ok=0
	for i in $(seq 1 180); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" = 1 ]; then
		# two draws per instance: confirms within-instance determinism still holds every time
		for k in 1 2; do
			curl -s -m 400 "http://127.0.0.1:$PORT/v1/chat/completions" \
				-H 'Content-Type: application/json' -d @"$PROBE" > "$OUT/${label}_r${rep}_d${k}.json"
		done
		local tg; tg=$(grep -oE 'tg = +[0-9.]+ t/s' "$slog" | tail -1)
		local acc; acc=$(grep -oE 'draft acceptance = [0-9.]+' "$slog" | tail -1)
		say "  $label rep$rep  $tg  ${acc:-}"
	else
		say "  $label rep$rep  FAILED TO START"
	fi
	# kill by captured PID only -- a pgrep/pkill -f pattern also matches this script's shell
	kill "$pid" 2>/dev/null
	for i in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 6
}

say "=== PAIRED MTP A/B, $REPS restarts per arm, alternating ==="
for r in $(seq 1 "$REPS"); do
	run_once base "$r"
	run_once mtp  "$r" --spec-type draft-mtp --spec-draft-n-max 2
done

say "=== ANALYSIS ==="
python3 - "$OUT" "$REPS" <<'PY' | tee -a "$LOG"
import json,hashlib,sys,os,itertools
d,reps=sys.argv[1],int(sys.argv[2])
def body(p):
    m=json.load(open(p))["choices"][0]["message"]
    return (m.get("reasoning_content") or "")+"|"+(m.get("content") or "")
H={}
for lab in ("base","mtp"):
    for r in range(1,reps+1):
        hs=[]
        for k in (1,2):
            p=os.path.join(d,"%s_r%d_d%d.json"%(lab,r,k))
            if os.path.exists(p):
                b=body(p); hs.append(hashlib.sha256(b.encode()).hexdigest()[:16])
        if hs:
            H.setdefault(lab,[]).append((r,hs))
            print("%-5s rep%d  draws=%s  within-instance=%s"%(
                lab,r,hs,"stable" if len(set(hs))==1 else "*** UNSTABLE ***"))
print()
for lab in ("base","mtp"):
    u=set(h[0] for _,h in H.get(lab,[]))
    print("%-5s distinct outputs across %d restarts: %d  %s"%(lab,len(H.get(lab,[])),len(u),sorted(u)))
b=set(h[0] for _,h in H.get("base",[])); m=set(h[0] for _,h in H.get("mtp",[]))
print()
if len(b)==1 and len(m)==1:
    print("VERDICT: each arm reproducible across restarts; arms %s -> difference IS attributable to MTP."
          %("DIFFER" if b!=m else "AGREE (MTP is lossless)"))
elif b & m:
    print("VERDICT: base and mtp produced OVERLAPPING outputs (%s) -> no MTP effect resolvable."%(b&m))
else:
    print("VERDICT: restart noise present (base has %d distinct, mtp %d). Arms share no output,"%(len(b),len(m)))
    print("         which is suggestive but NOT conclusive at this sample size.")
PY
say "=== DONE ==="
