#!/usr/bin/env bash
# Matched A/B: run the IDENTICAL frozen probe on the pre-VBR-pin commit (f7c420f8e) so the
# 23.72 t/s figure can be attributed to buun's VBR side-pin work rather than to a friendlier
# prompt. n=5 on the new build gave sd=0.03, so n=3 is ample here.
# ALWAYS restores master + a running server, even on failure.
set -u
R=~/buun_vbr
LOG=$R/matched_ab.log
log(){ echo "[$(date +%F_%T)] $*" | tee -a "$LOG"; }

restore() {
  log "RESTORE: returning to master and bringing the server back"
  git -C $R checkout -q master 2>>"$LOG"
  cmake --build $R/build -j 12 >> $R/ab_build_restore.log 2>&1
  pkill -f "buun_vbr/build/bin/llama-server" 2>/dev/null; sleep 5
  python3 - <<'PY' >> "$LOG" 2>&1
import json,os,subprocess
argv=json.load(open(os.path.expanduser("~/buun_vbr/argv_backup.json")))
out=open(os.path.expanduser("~/buun_vbr/server_restore.log"),"w")
subprocess.Popen(argv,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,
                 stdin=subprocess.DEVNULL)
PY
  log "RESTORE: server relaunched on master build (loading ~7min)"
  touch $R/ab.done
}
trap restore EXIT

log "=== matched A/B start; checking out f7c420f8e (pre-VBR-pin) ==="
git -C $R checkout -q f7c420f8e 2>>"$LOG" || { log "checkout FAILED"; exit 1; }
log "building old commit"
cmake --build $R/build -j 12 > $R/ab_build_old.log 2>&1 || { log "build FAILED"; exit 1; }
log "old build done"

pkill -f "buun_vbr/build/bin/llama-server" 2>/dev/null; sleep 5
python3 - <<'PY' >> "$LOG" 2>&1
import json,os,subprocess
argv=json.load(open(os.path.expanduser("~/buun_vbr/argv_backup.json")))
out=open(os.path.expanduser("~/buun_vbr/server_old.log"),"w")
subprocess.Popen(argv,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,
                 stdin=subprocess.DEVNULL)
PY
log "old server launched, waiting for health"

for i in $(seq 1 360); do
  curl -s -m 5 http://127.0.0.1:8082/health 2>/dev/null | grep -q '"status":"ok"' && break
  sleep 5
done
curl -s -m 5 http://127.0.0.1:8082/health | grep -q '"status":"ok"' \
  || { log "old server never healthy"; exit 2; }
log "old server healthy; running frozen probe n=3"

SRV=$R/server_old.log python3 - <<'PY' 2>&1 | tee -a "$LOG"
import json,os,re,statistics,urllib.request
SRV=os.environ["SRV"]
P="Count from one to forty in words, comma separated. Then say DONE."
EVAL=re.compile(r"eval time =\s*[\d.]+ ms /\s*\d+ tokens \(\s*[\d.]+ ms per token,\s*([\d.]+) tokens per second")
DRAFT=re.compile(r"(?:draft acceptance|accept(?:ance)? rate|n_accept)[^0-9]*([\d.]+)",re.I)
tps=[];acc=[]
for i in range(3):
    off=os.path.getsize(SRV)
    b=json.dumps({"messages":[{"role":"user","content":P}],"max_tokens":3000,
                  "temperature":0.0,"stream":False}).encode()
    rq=urllib.request.Request("http://127.0.0.1:8082/v1/chat/completions",data=b,
                              headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(rq,timeout=1800) as r: d=json.loads(r.read())
    c=d["choices"][0]["message"].get("content") or ""
    with open(SRV,errors="ignore") as f: f.seek(off); seg=f.read()
    e=EVAL.findall(seg); a=DRAFT.findall(seg)
    ok=bool(c.strip()) and "forty" in c and "DONE" in c
    t=float(e[-1]) if e else None
    print(f"OLD run{i+1}: ok={ok} t/s={t} draft={a[-1] if a else '-'} chars={len(c)}")
    if ok and t: tps.append(t); acc.append(float(a[-1]) if a else 0)
if len(tps)>=2:
    print(f"OLD RESULT n={len(tps)} mean={statistics.mean(tps):.2f} "
          f"sd={statistics.stdev(tps):.2f} | draft={statistics.mean(acc):.4f}")
    print(f"NEW (dd48dd86b) was: mean=23.72 sd=0.03 draft=0.9035")
else:
    print("OLD RESULT: insufficient coherent runs")
PY
log "=== probe complete, restoring ==="
