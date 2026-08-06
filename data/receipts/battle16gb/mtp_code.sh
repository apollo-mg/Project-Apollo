#!/usr/bin/env bash
# The code cell of the MTP structured-stability test, run properly.
#
# WHY THIS EXISTS. In mtp_structured.sh the code class came back VOID: at 900, 2000 and
# 4000 max_tokens BOTH arms hit finish_reason=length with content_chars=0. The model writes
# complete, working code INSIDE its <think> block and then keeps deliberating -- the tail of
# a 13,859-char reasoning trace is literally "But regex is more Pythonic for this". A
# stopping-rule failure, not a capability failure (same family as the Puzzle-75B HumanEval+
# finding). The extractor then returned the placeholder "<NO CODE BLOCK>" for every draw,
# which compares equal to itself and scored as STABLE -- a fake result, now flagged VOID.
#
# TWO FIXES:
#   1. enable_thinking:false via chat-template kwargs, so the answer is the output.
#   2. If content is still empty, fall back to extracting the LAST complete ```python block
#      from reasoning_content -- the code is genuinely there, and its stability is exactly
#      what we are trying to measure. Which source was used is REPORTED, never silently mixed.
#
# THE QUESTION (Mark): synonym swaps are innocent in prose, not in code. Code has far more
# near-tied token positions than a JSON argument does -- identifier names, `!=` vs `is not`,
# comprehension vs loop -- so this is the strongest remaining test of whether MTP's
# nondeterminism reaches output where a flip changes MEANING.
#
# Also scores each extracted function for CORRECTNESS, because a stable wrong answer and a
# stable right answer are very different results.
set -u
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/35B-A3B/Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
OUT=/home/mark/projects/HermesAgent-20/mtp_code
PORT=${PORT:-8112}
INSTANCES=${INSTANCES:-2}
DRAWS=${DRAWS:-3}
mkdir -p "$OUT"
LOG=$OUT/code.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
export LD_LIBRARY_PATH="$BIN:${LD_LIBRARY_PATH:-}"

cat > "$OUT/p_code.json" <<'EOF'
{"model":"q","temperature":0,"max_tokens":1500,"cache_prompt":false,
 "chat_template_kwargs":{"enable_thinking":false},
 "messages":[{"role":"user","content":"Write a Python function parse_iso8601_duration(s) that converts an ISO-8601 duration string like 'P3DT4H5M6S' into total seconds as an int. Handle days, hours, minutes and seconds. Reply with ONLY a single ```python code block and no other text."}]}
EOF

run_instance() {
	local label=$1 inst=$2; shift 2
	local slog=$OUT/server_${label}_${inst}.log
	setsid "$BIN/llama-server" -m "$MODEL" -c 65536 -b 1024 -ub 512 \
		-ctk f16 -ctv f16 -cb -fa on -np 1 -ngl 99 --cache-ram 0 \
		--port "$PORT" --host 127.0.0.1 --jinja "$@" \
		> "$slog" 2>&1 < /dev/null &
	local pid=$!
	local ok=0
	local i   # local: without it this clobbers the caller's instance counter (see mtp_structured.sh)
	for i in $(seq 1 180); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" = 1 ]; then
		local k
		for k in $(seq 1 "$DRAWS"); do
			curl -s -m 400 "http://127.0.0.1:$PORT/v1/chat/completions" \
				-H 'Content-Type: application/json' -d @"$OUT/p_code.json" \
				> "$OUT/${label}_i${inst}_${k}.json"
		done
		say "  $label inst$inst done  $(grep -oE 'draft acceptance = [0-9.]+' "$slog" | tail -1)"
	else
		say "  $label inst$inst FAILED TO START"; tail -8 "$slog" | tee -a "$LOG"
	fi
	kill "$pid" 2>/dev/null
	local w
	for w in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 6
}

say "=== CODE STABILITY: base vs MTP, ${INSTANCES}x${DRAWS}, thinking disabled ==="
for inst in $(seq 1 "$INSTANCES"); do
	run_instance base "$inst"
	run_instance mtp  "$inst" --spec-type draft-mtp --spec-draft-n-max 2
done

say "=== ANALYSIS ==="
python3 - "$OUT" "$INSTANCES" "$DRAWS" <<'PY' | tee -a "$LOG"
import json,hashlib,sys,os,re
d,INST,DR=sys.argv[1],int(sys.argv[2]),int(sys.argv[3])
BLOCK=re.compile(r"```(?:python)?\s*\n(.*?)```", re.S)

def grab(p):
    """(code, source, finish) -- source is reported, never silently mixed."""
    try: j=json.load(open(p))
    except Exception: return None,None,None
    ch=j["choices"][0]; m=ch["message"]; fin=ch.get("finish_reason")
    for src in ("content","reasoning_content"):
        t=m.get(src) or ""
        b=BLOCK.findall(t)
        if b: return b[-1].strip(), src, fin
    return None,None,fin

def works(code):
    """Does it actually parse P3DT4H5M6S -> 273906 and P1D -> 86400?"""
    ns={}
    try:
        exec(code, ns)
        f=ns.get("parse_iso8601_duration")
        if not f: return "no-func"
        checks=[("P3DT4H5M6S",3*86400+4*3600+5*60+6),("P1D",86400),("PT30S",30),("PT2H",7200)]
        return "correct" if all(f(a)==b for a,b in checks) else "wrong"
    except Exception as e:
        return "raises:%s"%type(e).__name__

rows={}
for arm in ("base","mtp"):
    for i in range(1,INST+1):
        for k in range(1,DR+1):
            c,src,fin=grab(os.path.join(d,"%s_i%d_%d.json"%(arm,i,k)))
            rows.setdefault(arm,[]).append((c,src,fin))

for arm in ("base","mtp"):
    got=[(c,s,f) for c,s,f in rows.get(arm,[]) if c]
    miss=len(rows.get(arm,[]))-len(got)
    if not got:
        print("%-5s NO CODE EXTRACTED in %d draws"%(arm,len(rows.get(arm,[])))); continue
    hs=[hashlib.sha256(c.encode()).hexdigest()[:12] for c,_,_ in got]
    srcs=set(s for _,s,_ in got); fins=set(f for _,_,f in got)
    verd=set(works(c) for c,_,_ in got)
    print("%-5s draws=%d missing=%d distinct=%d  source=%s finish=%s  correctness=%s"%(
        arm,len(got),miss,len(set(hs)),sorted(srcs),sorted(fins),sorted(verd)))
    if len(set(hs))>1:
        seen={}
        for c,_,_ in got: seen.setdefault(hashlib.sha256(c.encode()).hexdigest()[:12],c)
        keys=list(seen)
        a,b=seen[keys[0]].splitlines(),seen[keys[1]].splitlines()
        import difflib
        print("   first diff between two variants:")
        for ln in list(difflib.unified_diff(a,b,lineterm=""))[2:12]: print("     ",ln)

bh=set(hashlib.sha256(c.encode()).hexdigest()[:12] for c,_,_ in rows.get("base",[]) if c)
mh=set(hashlib.sha256(c.encode()).hexdigest()[:12] for c,_,_ in rows.get("mtp",[]) if c)
print()
if bh and mh:
    if len(bh)==1 and len(mh)==1:
        print("VERDICT: both arms stable; code %s across arms."%("IDENTICAL" if bh==mh else "DIFFERS"))
    else:
        print("VERDICT: base %d distinct, mtp %d distinct -> %s"%(
            len(bh),len(mh),"MTP destabilises code output" if len(mh)>len(bh) else "instability not MTP-specific"))
PY
say "=== DONE ==="
