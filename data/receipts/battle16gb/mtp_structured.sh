#!/usr/bin/env bash
# Does MTP's nondeterminism stay in prose, or does it reach tool calls and code?
#
# THE QUESTION (Mark, 2026-07-29): "replacing synonymous words in natural language is
# inherently innocent, not so in tool calls and coding."
#
# MTP_DETERMINISM.md established that --spec-type draft-mtp makes this server
# nondeterministic at temperature 0: 6 draws produced 4 distinct outputs, all diverging from
# base at the same token ("Key Aspects" -> "Key Areas"). That divergence was PROSE, where
# top-1 and top-2 are near-tied and either word is correct.
#
# MECHANISM UNDER TEST. If the flips are caused by float-reduction reordering under batched
# verification, they can only flip positions where the argmax MARGIN is tiny. Prose synonym
# slots are exactly that. A tool call's `{"city":` is not -- the next token there carries
# overwhelming probability mass. So the optimistic hypothesis is that structured output is
# intrinsically protected by its own low entropy.
# The pessimistic counter-hypothesis: code and JSON have plenty of near-tied positions too
# (identifier naming, key order, string contents), AND an early prose flip can propagate into
# a DIFFERENT ACTION downstream without any structured token being flipped directly -- we
# already saw one flip fan out into four different continuations.
#
# FOUR PROMPT CLASSES, hashed on the part that matters for each:
#   prose      free text                      -> hash whole body        (positive control:
#                                                                        must be unstable)
#   toolsimple unambiguous call, given args   -> hash tool_calls only
#   code       write a function               -> hash extracted code only
#   toolcalc   MUST COMPUTE the arguments     -> hash tool_calls only    (the dangerous case:
#                                                                        wrong number, not
#                                                                        wrong word)
#
# PREDICTIONS LOGGED BEFORE RUNNING (Claude, 2026-07-29):
#   P-M1 toolsimple args byte-stable under MTP, 6/6 ........................ 0.85
#   P-M2 code diverges under MTP at least once in 6 draws .................. 0.65
#   P-M3 toolcalc produces at least one WRONG or DIFFERING argument value ... 0.45
#   P-M4 base is stable in all four classes ................................ 0.95
# If P-M1 holds and P-M3 fails, Mark's concern is real in principle but bounded in practice
# on this model. If P-M3 fires, MTP is disqualifying for agentic work, not just for
# measurement.
#
# 2 server instances x 3 draws per arm: MTP proved unstable WITHIN an instance, and 3
# consecutive identical draws already fooled this campaign once (mtp_ab.sh).
set -u
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/35B-A3B/Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
OUT=/home/mark/projects/HermesAgent-20/mtp_structured
PORT=${PORT:-8111}
INSTANCES=${INSTANCES:-2}
DRAWS=${DRAWS:-3}
mkdir -p "$OUT"
LOG=$OUT/structured.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
export LD_LIBRARY_PATH="$BIN:${LD_LIBRARY_PATH:-}"

# cache_prompt:false so a warm slot cannot mask or manufacture a difference between draws.
cat > "$OUT/p_prose.json" <<'EOF'
{"model":"q","temperature":0,"max_tokens":3000,"cache_prompt":false,
 "messages":[{"role":"user","content":"Write a detailed technical explanation of how a B-tree index works in a relational database, covering node structure, splits, and range scans. Be thorough."}]}
EOF
cat > "$OUT/p_toolsimple.json" <<'EOF'
{"model":"q","temperature":0,"max_tokens":1200,"cache_prompt":false,
 "messages":[{"role":"user","content":"What is the weather in Tokyo right now? Use the tool."}],
 "tools":[{"type":"function","function":{"name":"get_weather","description":"Get current weather for a city","parameters":{"type":"object","properties":{"city":{"type":"string"},"unit":{"type":"string","enum":["c","f"]}},"required":["city"]}}}]}
EOF
cat > "$OUT/p_code.json" <<'EOF'
{"model":"q","temperature":0,"max_tokens":4000,"cache_prompt":false,
 "messages":[{"role":"user","content":"Write a Python function parse_iso8601_duration(s) that converts an ISO-8601 duration string like 'P3DT4H5M6S' into total seconds as an int. Handle days, hours, minutes, seconds. Return ONLY the code in a single ```python block, no explanation."}]}
EOF
# toolcalc: the arguments are COMPUTED, not copied. A flipped token here is a wrong number.
# Ground truth: severities 5+3+8+2+7+4+6 = 35 ; count 7 ; max owner "carol" (8).
cat > "$OUT/p_toolcalc.json" <<'EOF'
{"model":"q","temperature":0,"max_tokens":2600,"cache_prompt":false,
 "messages":[{"role":"user","content":"Here are incident records:\nalice sev=5\nbob sev=3\ncarol sev=8\nalice sev=2\ndave sev=7\nbob sev=4\ncarol sev=6\n\nCompute the total number of incidents, the sum of all severities, and the owner with the single highest individual severity value. Then call submit_summary with those exact values. Do not explain, just call the tool."}],
 "tools":[{"type":"function","function":{"name":"submit_summary","description":"Submit computed incident summary","parameters":{"type":"object","properties":{"total_incidents":{"type":"integer"},"total_severity":{"type":"integer"},"top_owner":{"type":"string"}},"required":["total_incidents","total_severity","top_owner"]}}}]}
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
	# `local i` is LOAD-BEARING: without it this clobbers the caller's instance counter and
	# both instances write to the same filenames, silently halving the sample. That bug made
	# the first run report 3 draws as 6.
	local i
	for i in $(seq 1 180); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" = 1 ]; then
		for cls in prose toolsimple code toolcalc; do
			for k in $(seq 1 "$DRAWS"); do
				curl -s -m 400 "http://127.0.0.1:$PORT/v1/chat/completions" \
					-H 'Content-Type: application/json' -d @"$OUT/p_${cls}.json" \
					> "$OUT/${label}_i${inst}_${cls}_${k}.json"
			done
		done
		say "  $label inst$inst done  $(grep -oE 'draft acceptance = [0-9.]+' "$slog" | tail -1)"
	else
		say "  $label inst$inst FAILED TO START"
	fi
	# kill by captured PID; a pgrep/pkill -f pattern also matches this script's own shell
	kill "$pid" 2>/dev/null
	local w
	for w in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
	kill -9 "$pid" 2>/dev/null; sleep 6
}

say "=== STRUCTURED-OUTPUT STABILITY: base vs MTP, ${INSTANCES}x${DRAWS} draws per class ==="
for i in $(seq 1 "$INSTANCES"); do
	run_instance base "$i"
	run_instance mtp  "$i" --spec-type draft-mtp --spec-draft-n-max 2
done

say "=== ANALYSIS ==="
python3 - "$OUT" "$INSTANCES" "$DRAWS" <<'PY' | tee -a "$LOG"
import json,hashlib,sys,os,re
d,INST,DR=sys.argv[1],int(sys.argv[2]),int(sys.argv[3])

def load(p):
    try: return json.load(open(p))
    except Exception: return None

TRUNC=[]
def extract(cls, j, tag=""):
    """Return the string that MATTERS for this class, or None."""
    if not j: return None
    if j["choices"][0].get("finish_reason")=="length":
        TRUNC.append(tag or cls)
    m=j["choices"][0]["message"]
    if cls in ("toolsimple","toolcalc"):
        tc=m.get("tool_calls")
        if not tc: return "<NO TOOL CALL>"
        # name + arguments only: reasoning prose is deliberately excluded
        return json.dumps([{"n":c["function"]["name"],"a":c["function"]["arguments"]} for c in tc],
                          sort_keys=True)
    if cls=="code":
        c=m.get("content") or ""
        b=re.search(r"```(?:python)?\n(.*?)```", c, re.S)
        return b.group(1).strip() if b else "<NO CODE BLOCK>"  # counted as void below
    return (m.get("reasoning_content") or "")+"|"+(m.get("content") or "")

print("%-11s %-5s %-8s %s"%("class","arm","distinct","detail"))
summary={}
for cls in ("prose","toolsimple","code","toolcalc"):
    for arm in ("base","mtp"):
        vals=[]
        for i in range(1,INST+1):
            for k in range(1,DR+1):
                j=load(os.path.join(d,"%s_i%d_%s_%d.json"%(arm,i,cls,k)))
                v=extract(cls,j,"%s_i%d_%s_%d"%(arm,i,cls,k))
                if v is not None: vals.append(v)
        if not vals: continue
        hs=[hashlib.sha256(v.encode()).hexdigest()[:12] for v in vals]
        n=len(set(hs))
        summary[(cls,arm)]=(n,len(vals),vals)
        void = vals[0] in ("<NO CODE BLOCK>","<NO TOOL CALL>") and n==1
        flag=("*** VOID: %s -- class produced no usable output ***"%vals[0]) if void else (
             "STABLE" if n==1 else "*** %d VARIANTS ***"%n)
        print("%-11s %-5s %-8s %s"%(cls,arm,"%d/%d"%(n,len(vals)),flag))

if TRUNC:
    print("\n*** TRUNCATED (finish_reason=length) -- these draws are budget artifacts, not content differences:")
    for t in TRUNC: print("      ",t)
print("\n--- tool call argument values (the part that must not drift) ---")
for cls in ("toolsimple","toolcalc"):
    for arm in ("base","mtp"):
        if (cls,arm) not in summary: continue
        n,tot,vals=summary[(cls,arm)]
        uniq=[]
        for v in vals:
            if v not in uniq: uniq.append(v)
        for v in uniq:
            print("  %-11s %-5s %s"%(cls,arm,v[:170]))

print("\n--- correctness of computed arguments (ground truth: 7 incidents, severity 35, carol) ---")
for arm in ("base","mtp"):
    if ("toolcalc",arm) not in summary: continue
    n,tot,vals=summary[("toolcalc",arm)]
    ok=bad=0
    for v in vals:
        try:
            a=json.loads(json.loads(v)[0]["a"])
            good=(int(a.get("total_incidents",-1))==7 and int(a.get("total_severity",-1))==35
                  and str(a.get("top_owner","")).lower()=="carol")
        except Exception:
            good=False
        ok+=good; bad+= (not good)
    print("  %-5s correct %d / %d draws"%(arm,ok,ok+bad))
PY
say "=== DONE ==="
