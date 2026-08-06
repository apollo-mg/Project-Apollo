#!/usr/bin/env bash
# How big is the perturbation MTP actually introduces? Two competing stories:
#
#   (1) TINY + SENSITIVE. Batched verification changes float reduction order by a hair. It can
#       only flip the argmax where top-1 and top-2 are already within float noise. Everything
#       downstream is the model correctly continuing from different text. Inherent to
#       speculative decoding, not a bug.
#   (2) BIG. The perturbation is far larger than float noise, i.e. something in the MTP path
#       is substantively wrong. Then it is a defect to report, not a property to document.
#
# Mark's objection ("doesn't feel like that should invoke enough noise to cause such a
# cascade") is the right challenge: I asserted "one ULP" rhetorically without measuring it.
# Batched accumulation across 40 layers at ~2.5 bpw could be much larger than one ULP.
#
# THE DECIDING MEASUREMENT: the logit margin at the position where the two arms disagree.
# Story (1) predicts the flip lands where margin ~ float noise (say < 1e-3 in logprob).
# Story (2) predicts flips at positions with comfortable margins.
#
# METHOD. Same prompt both arms, n_probs on, temperature 0. Walk the two token streams
# together. At the FIRST position where the chosen tokens differ, record:
#   - each arm's top-2 tokens and logprobs
#   - the margin (top1 - top2) in each arm
#   - whether the two arms' top-2 SETS agree (they should: same candidates, different order)
# Also record the margin distribution over ALL agreeing positions, so "the flip happened at
# an unusually tight position" is a claim with a reference distribution behind it.
set -u
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/35B-A3B/Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
OUT=/home/mark/projects/HermesAgent-20/mtp_margin
PORT=${PORT:-8115}
mkdir -p "$OUT"
LOG=$OUT/margin.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
export LD_LIBRARY_PATH="$BIN:${LD_LIBRARY_PATH:-}"

# The prose prompt is used because it is the one that RELIABLY diverges (MTP_DETERMINISM.md:
# "Key Aspects" -> "Key Areas" at char 126, reproduced in 4/4 MTP variants). A prompt that
# does not diverge cannot locate a flip.
cat > "$OUT/probe.json" <<'EOF'
{"model":"q","temperature":0,"max_tokens":400,"cache_prompt":false,"n_probs":5,
 "messages":[{"role":"user","content":"Write a detailed technical explanation of how a B-tree index works in a relational database, covering node structure, splits, and range scans. Be thorough."}]}
EOF

run() {
	local label=$1; shift
	local slog=$OUT/server_${label}.log
	setsid "$BIN/llama-server" -m "$MODEL" -c 65536 -b 1024 -ub 512 \
		-ctk f16 -ctv f16 -cb -fa on -np 1 -ngl 99 --cache-ram 0 \
		--port "$PORT" --host 127.0.0.1 --jinja "$@" > "$slog" 2>&1 < /dev/null &
	local pid=$!
	local i ok=0
	for i in $(seq 1 180); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" = 1 ]; then
		curl -s -m 400 "http://127.0.0.1:$PORT/v1/completions" \
			-H 'Content-Type: application/json' \
			-d "$(python3 -c "
import json
d=json.load(open('$OUT/probe.json'))
# /v1/completions exposes per-token logprobs reliably; build the prompt via the chat template
print(json.dumps({'model':'q','temperature':0,'max_tokens':400,'cache_prompt':False,'n_probs':5,
 'prompt':'<|im_start|>user\n'+d['messages'][0]['content']+'<|im_end|>\n<|im_start|>assistant\n'}))")" \
			> "$OUT/${label}.json"
		say "  $label captured ($(python3 -c "
import json;d=json.load(open('$OUT/${label}.json'))
print(len(d.get('completion_probabilities') or []),'positions')" 2>/dev/null || echo '?'))"
	else
		say "  $label FAILED TO START"; tail -8 "$slog" | tee -a "$LOG"
	fi
	kill "$pid" 2>/dev/null
	local w; for w in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 6
}

say "=== LOGIT MARGIN AT DIVERGENCE: base vs MTP ==="
run base
run mtp --spec-type draft-mtp --spec-draft-n-max 2

say "=== ANALYSIS ==="
python3 - "$OUT" <<'PY' | tee -a "$LOG"
import json,sys,os
d=sys.argv[1]
def probs(p):
    j=json.load(open(os.path.join(d,p)))
    return j.get("completion_probabilities") or []
try:
    B,M=probs("base.json"),probs("mtp.json")
except Exception as e:
    print("could not load:",e); raise SystemExit

def top(entry):
    """(chosen_token, [(tok,logprob)...]) sorted desc."""
    ch=entry.get("token") if "token" in entry else entry.get("content")
    cand=entry.get("top_logprobs") or entry.get("probs") or []
    out=[]
    for c in cand:
        t=c.get("token") if "token" in c else c.get("tok_str")
        lp=c.get("logprob")
        if lp is None and c.get("prob") is not None:
            import math; lp=math.log(max(c["prob"],1e-30))
        out.append((t,lp))
    out.sort(key=lambda x:-(x[1] if x[1] is not None else -1e9))
    return ch,out

print("positions: base=%d mtp=%d"%(len(B),len(M)))
margins=[]
flip=None
for i in range(min(len(B),len(M))):
    cb,tb=top(B[i]); cm,tm=top(M[i])
    if len(tb)>=2 and tb[0][1] is not None and tb[1][1] is not None:
        margins.append(tb[0][1]-tb[1][1])
    if cb!=cm and flip is None:
        flip=(i,cb,cm,tb,tm)

if margins:
    s=sorted(margins)
    n=len(s)
    print("base top1-top2 logprob margin over %d agreeing positions:"%n)
    print("   min=%.6f  p10=%.4f  median=%.4f  p90=%.4f  max=%.4f"%(
        s[0],s[int(n*.1)],s[n//2],s[int(n*.9)],s[-1]))
    tight=sum(1 for x in s if x<0.01)
    print("   positions with margin < 0.01 logprob: %d (%.1f%%)"%(tight,100*tight/n))

if flip is None:
    print("\nNO DIVERGENCE in the captured window -- cannot locate a flip.")
else:
    i,cb,cm,tb,tm=flip
    print("\nFIRST DIVERGENCE at position %d"%i)
    print("  base chose %r ; mtp chose %r"%(cb,cm))
    print("  base top-5:", [(t,round(lp,6) if lp is not None else None) for t,lp in tb[:5]])
    print("  mtp  top-5:", [(t,round(lp,6) if lp is not None else None) for t,lp in tm[:5]])
    if len(tb)>=2 and tb[0][1] is not None and tb[1][1] is not None:
        mgn=tb[0][1]-tb[1][1]
        print("  BASE MARGIN AT FLIP: %.8f logprob"%mgn)
        rank=sum(1 for x in margins if x<mgn)
        print("  -> tighter than %.1f%% of all positions"%(100*rank/len(margins)))
        print()
        if mgn < 0.01:
            print("  VERDICT: flip occurred at a near-tie. Consistent with a TINY perturbation")
            print("           amplified by a genuinely ambiguous choice -- inherent to batched")
            print("           verification, not evidence of a broken MTP path.")
        else:
            print("  VERDICT: flip occurred at a COMFORTABLE margin (%.4f). Float-reduction"%mgn)
            print("           noise should not move this. Suggests the MTP path perturbs logits")
            print("           substantively -- a defect worth reporting upstream.")
    sb={t for t,_ in tb[:5]}; sm={t for t,_ in tm[:5]}
    print("\n  top-5 candidate sets %s (overlap %d/5)"%(
        "AGREE" if sb==sm else "DIFFER", len(sb&sm)))
    print("  (same candidates in a different order = reordering; different candidates =")
    print("   the distribution itself moved, which is the stronger signal of a real defect)")
PY
say "=== DONE ==="
