#!/usr/bin/env python3
"""n=5 repeats of the counting probe on the current build, to separate a real gain from
noise. Frozen as the standard harness so the sharding build gets a matched A/B."""
import json, os, re, statistics, time, urllib.request
BASE="http://127.0.0.1:8082"; SRV=os.path.expanduser("~/buun_vbr/server_new.log")
LOG=os.path.expanduser("~/buun_vbr/repeat.log")
P="Count from one to forty in words, comma separated. Then say DONE."
EVAL=re.compile(r"eval time =\s*[\d.]+ ms /\s*\d+ tokens \(\s*[\d.]+ ms per token,\s*([\d.]+) tokens per second")
DRAFT=re.compile(r"(?:draft acceptance|accept(?:ance)? rate|n_accept)[^0-9]*([\d.]+)",re.I)
def log(m):
    l=f"[{time.strftime('%F %T')}] {m}"; print(l,flush=True)
    open(LOG,"a").write(l+"\n")
tps=[]; acc=[]
for i in range(5):
    off=os.path.getsize(SRV)
    body=json.dumps({"messages":[{"role":"user","content":P}],"max_tokens":3000,
                     "temperature":0.0,"stream":False}).encode()
    r=urllib.request.Request(f"{BASE}/v1/chat/completions",data=body,
                             headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=1800) as resp: d=json.loads(resp.read())
    c=d["choices"][0]["message"].get("content") or ""
    seg=open(SRV,errors="ignore").read()[off:] if True else ""
    with open(SRV,errors="ignore") as f: f.seek(off); seg=f.read()
    e=EVAL.findall(seg); a=DRAFT.findall(seg)
    ok = bool(c.strip()) and "forty" in c and "DONE" in c
    t=float(e[-1]) if e else None
    log(f"run{i+1}: ok={ok} t/s={t} draft={a[-1] if a else '-'} content_chars={len(c)}")
    if ok and t: tps.append(t); acc.append(float(a[-1]) if a else 0)
if len(tps)>=2:
    log(f"RESULT n={len(tps)} mean={statistics.mean(tps):.2f} sd={statistics.stdev(tps):.2f} "
        f"min={min(tps):.2f} max={max(tps):.2f} | mean draft acc={statistics.mean(acc):.4f}")
else:
    log("RESULT insufficient coherent runs")
