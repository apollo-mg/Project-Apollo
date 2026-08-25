#!/usr/bin/env python3
"""Run one fidelity arm: fill to the target bitrate, verify achieved kv_bpv, then measure."""
import json, subprocess, sys, time, urllib.request
HOST=f"http://10.0.0.194:8100"
LABEL=sys.argv[1]; TARGET=float(sys.argv[2]) if len(sys.argv)>2 else None

def slots():
    s=json.load(urllib.request.urlopen(HOST+"/slots",timeout=30))
    return s[0] if isinstance(s,list) and s else s
def ask(msg,n,seed=1001,cache=True):
    b={"messages":[{"role":"user","content":msg}],"n_predict":n,"temperature":1.0,
       "top_p":0.95,"top_k":20,"seed":seed,"cache_prompt":cache,
       # AFM-23: unset resolves to xhigh (5.85x cost, destabilises the unanswerable arm).
       # Pin medium — the unmodified model, no injected system text.
       "chat_template_kwargs":{"reasoning_effort":"medium"}}
    r=urllib.request.Request(HOST+"/v1/chat/completions",data=json.dumps(b).encode(),
                             headers={"Content-Type":"application/json"})
    t0=time.time()
    d=json.loads(urllib.request.urlopen(r,timeout=2400).read())
    m=d["choices"][0]["message"]
    return (m.get("content") or ""),(m.get("reasoning_content") or ""),d["choices"][0].get("finish_reason"),time.time()-t0,(d.get("usage") or {})

FILL=("Section %d. The subsystem records ambient telemetry at fixed intervals and forwards it to "
      "the aggregator, which reconciles clock drift before persisting to the archive tier. ")
hist=""; achieved=slots().get("kv_bpv")
if TARGET:
    for step in range(1,40):
        hist += FILL % step * 60
        _,_,_,_,u = ask(hist+"\nReply: ok",8)
        achieved=slots().get("kv_bpv")
        if achieved is not None and achieved <= TARGET*1.02: break
print(f"  achieved kv_bpv = {achieved}  (target {TARGET})  ctx≈{u.get('prompt_tokens',0) if TARGET else 0:,}")

# LIVENESS at depth (AFM-21: fidelity metrics cannot see this)
c,r,fin,dt,u = ask(hist+"\n\nWrite 400 words on how a KV cache is laid out in memory.",500)
txt=c+r; bang=txt.count("!")/max(len(txt),1)
c2,r2,_,_,_ = ask(hist+"\n\nWhat is 17 multiplied by 23? Answer with the number only.",256)
print(f"  liveness: !frac={bang:.3f}  canary_391={'391' in (c2+r2)}  tps={u.get('completion_tokens',0)/dt if dt else 0:.2f}")

# tier_cal, 3 seeds, at this depth
fx=json.load(open("../viability/fixture_v0_beta.json"))["tier_cal"]
import re
ANS=re.compile(r"Exact Answer\s*:\s*(.+?)(?:\n|$)",re.I)
res=[]
for seed in (1001,1002,1003):
    for it in fx["items"]:
        c,r,fin,_,_ = ask(hist+"\n\n"+fx["prompt"].format(q=it["q"]),3072,seed)
        for t in (c, r if fin!="length" else ""):
            ms=ANS.findall(t or "")
            if ms: ans=ms[-1].strip(); break
        else: ans=""
        v=("NO-STOP" if fin=="length" and not ans else
           "ABSTAINED" if ans.upper().startswith("UNKNOWN") else
           "ANSWERED-WRONG" if ans else "NO-ANSWER")
        if it["gold"]!="UNKNOWN" and ans and not ans.upper().startswith("UNKNOWN"):
            v = "ANSWERED-CORRECT" if it["gold"].lower() in ans.lower() else "ANSWERED-WRONG"
        res.append(dict(arm=LABEL,seed=seed,id=it["id"],arm_type=it["arm"],verdict=v,ans=ans[:60],
                        kv_bpv=achieved))
        with open(f"fid_{LABEL}.jsonl","a") as f:
            f.write(json.dumps(res[-1])+"\n"); f.flush()
from collections import Counter
U=[x for x in res if x["arm_type"]=="unanswerable"]; A=[x for x in res if x["arm_type"]=="answerable"]
cu=Counter(x["verdict"] for x in U); ca=Counter(x["verdict"] for x in A)
print(f"  tier_cal: confab {cu['ANSWERED-WRONG']}/{len(U)}  abstain {cu['ABSTAINED']}/{len(U)}  "
      f"acc {ca['ANSWERED-CORRECT']}/{len(A)}  no-stop {cu['NO-STOP']+ca['NO-STOP']}")
