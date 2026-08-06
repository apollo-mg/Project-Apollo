#!/usr/bin/env bash
# Is MTP's code defect DIRECTIONAL, or did one draw happen to land wrong?
#
# WHAT WE HAVE (mtp_code.sh, n=1 prompt): on parse_iso8601_duration, base produced correct
# code in 6/6 draws and MTP produced code that raises ValueError in 6/6 draws. The single
# substantive difference is a dropped `T` separator in the regex:
#     base  ^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$    correct on 4/4 cases
#     mtp   ^P(?:(?:(\d+)D)?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)$      fails 3/4, incl. the
#                                                                    example in the prompt
# Each arm is internally stable; the arms differ. That is a real, reproducible divergence in
# semantically load-bearing output -- exactly Mark's point that a synonym swap is innocent in
# prose and not in code.
#
# BUT n=1 PROMPT CANNOT SUPPORT "MTP DEGRADES CODE". Speculative decoding shifts which
# trajectory is emitted; on one task that shift can land on a worse answer by chance. To
# claim a direction we need several independent tasks and a count of which arm is correct.
# Null hypothesis: MTP changes code but wins and loses about equally often.
#
# 6 tasks x 2 instances x 2 draws per arm. Each task has executable ground truth, so
# "different" and "wrong" stay separate measurements -- the whole point.
set -u
BIN=/mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant/build/bin
MODEL="/mnt/TG_2TB/AI/Models/Qwen 3.5/35B-A3B/Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
OUT=/home/mark/projects/HermesAgent-20/mtp_code_multi
PORT=${PORT:-8113}
INSTANCES=${INSTANCES:-2}
DRAWS=${DRAWS:-2}
mkdir -p "$OUT"
LOG=$OUT/multi.log
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
export LD_LIBRARY_PATH="$BIN:${LD_LIBRARY_PATH:-}"

# Tasks chosen to be short enough to finish without thinking, and to have crisp edge cases
# where a single dropped token changes behaviour (separators, boundaries, escapes).
mk() { # $1=name $2=prompt
	python3 - "$OUT/p_$1.json" "$2" <<'PY'
import json,sys
p,prompt=sys.argv[1],sys.argv[2]
json.dump({"model":"q","temperature":0,"max_tokens":1500,"cache_prompt":False,
 "chat_template_kwargs":{"enable_thinking":False},
 "messages":[{"role":"user","content":prompt+" Reply with ONLY a single ```python code block and no other text."}]},
 open(p,"w"))
PY
}
mk iso "Write a Python function parse_iso8601_duration(s) that converts an ISO-8601 duration string like 'P3DT4H5M6S' into total seconds as an int. Handle days, hours, minutes and seconds."
mk semver "Write a Python function compare_semver(a, b) that compares two semantic version strings like '1.2.10' and '1.10.2', returning -1, 0 or 1. Numeric components must compare numerically, not lexically."
mk csvq "Write a Python function split_csv_line(line) that splits a single CSV line into a list of fields, correctly handling double-quoted fields that contain commas, and doubled quotes as an escaped quote."
mk ipv4 "Write a Python function is_valid_ipv4(s) that returns True only for a valid dotted-quad IPv4 address: exactly four parts, each an integer 0-255, no leading zeros allowed except the single digit '0'."
mk roman "Write a Python function roman_to_int(s) that converts a Roman numeral string like 'MCMXCIV' to an integer, handling subtractive pairs such as IV, IX, XL, XC, CD and CM."
mk pathnorm "Write a Python function normalize_path(p) that simplifies a Unix absolute path string, resolving '.' and '..' components and collapsing repeated slashes, returning the canonical path. Do not touch the filesystem."

TASKS="iso semver csvq ipv4 roman pathnorm"

run_instance() {
	local label=$1 inst=$2; shift 2
	local slog=$OUT/server_${label}_${inst}.log
	setsid "$BIN/llama-server" -m "$MODEL" -c 65536 -b 1024 -ub 512 \
		-ctk f16 -ctv f16 -cb -fa on -np 1 -ngl 99 --cache-ram 0 \
		--port "$PORT" --host 127.0.0.1 --jinja "$@" \
		> "$slog" 2>&1 < /dev/null &
	local pid=$!
	local ok=0
	local i   # local: otherwise this clobbers the caller's instance counter
	for i in $(seq 1 180); do
		curl -s -m 5 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok"' && { ok=1; break; }
		kill -0 "$pid" 2>/dev/null || break
		sleep 2
	done
	if [ "$ok" = 1 ]; then
		local t k
		for t in $TASKS; do
			for k in $(seq 1 "$DRAWS"); do
				curl -s -m 400 "http://127.0.0.1:$PORT/v1/chat/completions" \
					-H 'Content-Type: application/json' -d @"$OUT/p_${t}.json" \
					> "$OUT/${label}_i${inst}_${t}_${k}.json"
			done
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

say "=== MULTI-TASK CODE: base vs MTP, 6 tasks x ${INSTANCES}x${DRAWS} ==="
for inst in $(seq 1 "$INSTANCES"); do
	run_instance base "$inst"
	run_instance mtp  "$inst" --spec-type draft-mtp --spec-draft-n-max 2
done

say "=== ANALYSIS ==="
python3 - "$OUT" "$INSTANCES" "$DRAWS" <<'PY' | tee -a "$LOG"
import json,hashlib,sys,os,re
d,INST,DR=sys.argv[1],int(sys.argv[2]),int(sys.argv[3])
BLOCK=re.compile(r"```(?:python)?\s*\n(.*?)```", re.S)
TASKS=["iso","semver","csvq","ipv4","roman","pathnorm"]

CASES={
 "iso":("parse_iso8601_duration",[("P3DT4H5M6S",273906),("P1D",86400),("PT30S",30),("PT2H",7200)]),
 "semver":("compare_semver",[(("1.2.10","1.10.2"),-1),(("2.0.0","2.0.0"),0),(("1.0.1","1.0.0"),1),(("1.10.0","1.9.0"),1)]),
 "csvq":("split_csv_line",[('a,b,c',["a","b","c"]),('"x,y",z',["x,y","z"]),('"he said ""hi""",q',['he said "hi"',"q"])]),
 "ipv4":("is_valid_ipv4",[("192.168.1.1",True),("256.1.1.1",False),("01.2.3.4",False),("0.0.0.0",True),("1.2.3",False)]),
 "roman":("roman_to_int",[("MCMXCIV",1994),("IV",4),("XL",40),("MMXXVI",2026),("III",3)]),
 "pathnorm":("normalize_path",[("/a/./b/../c","/a/c"),("//x//y","/x/y"),("/a/b/../..","/"),("/../","/")]),
}

def grab(p):
    try: j=json.load(open(p))
    except Exception: return None
    m=j["choices"][0]["message"]
    for src in ("content","reasoning_content"):
        b=BLOCK.findall(m.get(src) or "")
        if b: return b[-1].strip()
    return None

def verdict(task,code):
    if not code: return "nocode"
    fn,cases=CASES[task]; ns={}
    try: exec(code,ns)
    except Exception as e: return "exec:%s"%type(e).__name__
    f=ns.get(fn)
    if not f: return "nofunc"
    for a,e in cases:
        try:
            r=f(*a) if isinstance(a,tuple) else f(a)
        except Exception as ex: return "raises"
        if r!=e: return "wrong"
    return "correct"

score={"base":0,"mtp":0}; tot={"base":0,"mtp":0}
print("%-9s %-5s %-9s %-9s %s"%("task","arm","distinct","correct","verdicts"))
diffs=[]
for t in TASKS:
    per={}
    for arm in ("base","mtp"):
        codes=[]
        for i in range(1,INST+1):
            for k in range(1,DR+1):
                c=grab(os.path.join(d,"%s_i%d_%s_%d.json"%(arm,i,t,k)))
                if c: codes.append(c)
        vs=[verdict(t,c) for c in codes]
        hs=set(hashlib.sha256(c.encode()).hexdigest()[:10] for c in codes)
        ok=sum(1 for v in vs if v=="correct")
        score[arm]+=ok; tot[arm]+=len(vs)
        per[arm]=(hs,vs,codes)
        print("%-9s %-5s %-9s %-9s %s"%(t,arm,"%d/%d"%(len(hs),len(vs)),"%d/%d"%(ok,len(vs)),sorted(set(vs))))
    if per["base"][0] and per["mtp"][0] and per["base"][0]!=per["mtp"][0]:
        bo=sum(1 for v in per["base"][1] if v=="correct")/max(1,len(per["base"][1]))
        mo=sum(1 for v in per["mtp"][1] if v=="correct")/max(1,len(per["mtp"][1]))
        diffs.append((t,bo,mo))

print("\nTOTAL correct: base %d/%d   mtp %d/%d"%(score["base"],tot["base"],score["mtp"],tot["mtp"]))
print("\ntasks where the arms produced DIFFERENT code:")
bw=mw=tie=0
for t,bo,mo in diffs:
    tag = "base better" if bo>mo else ("mtp better" if mo>bo else "same correctness")
    bw+= bo>mo; mw+= mo>bo; tie+= bo==mo
    print("  %-9s base %.0f%% vs mtp %.0f%%   -> %s"%(t,bo*100,mo*100,tag))
print("\ndirection: base better on %d, mtp better on %d, equal on %d (of %d differing tasks)"%(bw,mw,tie,len(diffs)))
if bw+mw==0:
    print("=> MTP changes code WITHOUT changing correctness on these tasks.")
elif bw>mw:
    print("=> suggests MTP degrades code quality, not merely alters it.")
else:
    print("=> no evidence MTP degrades code; differences look direction-free.")
PY
say "=== DONE ==="
