#!/usr/bin/env python3
"""Does VBR damage what was ALREADY cached when it demotes a region?

Mark's point: an MP3 encoder decides allocation once, offline. VBR-KV is online and
path-dependent — early tokens live at f16 until pressure forces a demotion, and the source
calls that out as imprinting "irreversible re-encode error into existing tokens".

No single-point fidelity measurement can see this. The test:
  1. plant a fact at LOW position, ask about it while the region is still high-precision
  2. fill until the budget forces that region down several tiers
  3. ask the SAME question again

A flat codec cannot exhibit this — it was always at rate. If recall degrades only under VBR,
that is the re-encode cost, and it is the real thing a variable-rate ONLINE codec risks.
"""
import json, sys, time, urllib.request
HOST=f"http://10.0.0.194:{sys.argv[1] if len(sys.argv)>1 else 8100}"
LABEL=sys.argv[2] if len(sys.argv)>2 else "arm"

FACTS=[("The calibration constant for the Vestergaard array is 8417.","calibration constant for the Vestergaard array","8417"),
       ("Technician Rowe signed off on bay 12 at 03:47.","who signed off on bay 12","Rowe"),
       ("The archive tier retains records for 91 days.","how many days does the archive tier retain records","91")]
PLANT = "\n".join(f"NOTE {i+1}: {f[0]}" for i,f in enumerate(FACTS))

def slots():
    s=json.load(urllib.request.urlopen(HOST+"/slots",timeout=30))
    return s[0] if isinstance(s,list) and s else s
def ask(msg,n=256,seed=1001):
    b={"messages":[{"role":"user","content":msg}],"n_predict":n,"temperature":1.0,"top_p":0.95,
       "top_k":20,"seed":seed,"cache_prompt":True,
       "chat_template_kwargs":{"reasoning_effort":"medium"}}
    r=urllib.request.Request(HOST+"/v1/chat/completions",data=json.dumps(b).encode(),
                             headers={"Content-Type":"application/json"})
    d=json.loads(urllib.request.urlopen(r,timeout=1800).read())
    m=d["choices"][0]["message"]
    return (m.get("content") or "")+(m.get("reasoning_content") or ""), (d.get("usage") or {})

def recall(hist, tag):
    hits=[]
    for _,q,gold in FACTS:
        txt,u = ask(hist+f"\n\nFrom the notes above: {q}? Answer with the value only.")
        hits.append(gold.lower() in txt.lower())
    s=slots()
    print(f"  {tag:<22} recall {sum(hits)}/{len(FACTS)}  kv_bpv={s.get('kv_bpv')}  "
          f"ctx={u.get('prompt_tokens',0):,}", flush=True)
    return sum(hits), s.get("kv_bpv")

FILL=("Section %d. The subsystem records ambient telemetry at fixed intervals and forwards it to "
      "the aggregator, which reconciles clock drift before persisting to the archive tier. ")
hist = PLANT
print(f"=== {LABEL} ===")
r0,b0 = recall(hist, "before fill")
for step in range(1,40):
    hist += "\n" + FILL % step * 60
    _,u = ask(hist+"\nReply: ok", 8)
    if u.get("prompt_tokens",0) >= 29000: break
r1,b1 = recall(hist, "after fill")
print(f"  -> recall {r0}/{len(FACTS)} @ {b0} bpv  ->  {r1}/{len(FACTS)} @ {b1} bpv")
json.dump(dict(arm=LABEL,before=r0,bpv_before=b0,after=r1,bpv_after=b1),
          open(f"reencode_{LABEL}.json","w"), indent=1)
