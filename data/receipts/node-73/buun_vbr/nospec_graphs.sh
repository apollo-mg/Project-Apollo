#!/usr/bin/env bash
# Graphs DO engage on sm_60 when forced (5730 "warmup complete") but get invalidated almost
# as often (4688 "warmup reset") -> net zero. Hypothesis: MTP's variable draft-accept length
# changes graph properties every step, so capture cost cancels replay benefit.
# Test: same config with speculation REMOVED (stable shapes), graphs off vs on.
set -u
R=~/buun_vbr; LOG=$R/nospec.log
log(){ echo "[$(date +%F_%T)] $*" | tee -a "$LOG"; }
run_leg(){ # tag force
  pgrep -f "[b]uun_vbr/build/bin/llama-server" | while read p; do kill -9 "$p"; done; sleep 6
  TAG="$1" FORCE="$2" python3 - <<'PY'
import json,os,subprocess
argv=json.load(open(os.path.expanduser("~/buun_vbr/argv_backup.json")))
out=[];skip=0
for a in argv:                      # strip speculative decoding flags
    if skip: skip=0; continue
    if a in ("--spec-type","--spec-draft-n-max"): skip=1; continue
    out.append(a)
out += ["-lv","10"]
env=dict(os.environ)
if os.environ["FORCE"]=="1": env["GGML_CUDA_FORCE_GRAPHS"]="1"
else: env.pop("GGML_CUDA_FORCE_GRAPHS",None)
f=open(os.path.expanduser(f"~/buun_vbr/server_nospec_{os.environ['TAG']}.log"),"w")
subprocess.Popen(out,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,
                 stdin=subprocess.DEVNULL,env=env)
PY
  for i in $(seq 1 400); do
    curl -s -m 5 http://127.0.0.1:8082/health 2>/dev/null | grep -q '"status":"ok"' && break; sleep 5
  done
  curl -s -m 5 http://127.0.0.1:8082/health | grep -q '"status":"ok"' || { log "$1: never healthy"; return 1; }
  log "$1: healthy"
  SRV=$R/server_nospec_$1.log TAG="$1" python3 - <<'PY' | tee -a "$LOG"
import json,os,re,statistics,urllib.request
SRV=os.environ["SRV"];TAG=os.environ["TAG"]
P="Count from one to forty in words, comma separated. Then say DONE."
EVAL=re.compile(r"eval time =\s*[\d.]+ ms /\s*\d+ tokens \(\s*[\d.]+ ms per token,\s*([\d.]+) tokens per second")
t=[]
for i in range(4):
    off=os.path.getsize(SRV)
    b=json.dumps({"messages":[{"role":"user","content":P}],"max_tokens":3000,
                  "temperature":0.0,"stream":False}).encode()
    rq=urllib.request.Request("http://127.0.0.1:8082/v1/chat/completions",data=b,
                              headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(rq,timeout=1800) as r: d=json.loads(r.read())
    c=d["choices"][0]["message"].get("content") or ""
    with open(SRV,errors="ignore") as f: f.seek(off); seg=f.read()
    e=EVAL.findall(seg); ok=bool(c.strip()) and "forty" in c and "DONE" in c
    v=float(e[-1]) if e else None
    print(f"  {TAG} run{i+1}: coherent={ok} t/s={v}")
    if ok and v: t.append(v)
if len(t)>=2: print(f"  {TAG} RESULT n={len(t)} mean={statistics.mean(t):.2f} sd={statistics.stdev(t):.2f}")
PY
  log "$1 graph stats: complete=$(grep -c 'warmup complete' $R/server_nospec_$1.log) reset=$(grep -c 'warmup reset' $R/server_nospec_$1.log)"
}
log "=== no-speculation graphs A/B ==="
run_leg nospec_off 0
run_leg nospec_on 1
log "=== done (MTP reference: 23.79 warm, both graph states) ==="
touch $R/nospec.done
