#!/usr/bin/env python3
"""Hard questions, medium vs xhigh. See PREREG_HARD.md. Persists per item (standing rule)."""
import json, os, sys, urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://10.0.0.194:8081"
SINK = open("hard_results.jsonl", "a", encoding="utf-8")
ITEMS = [
 ("H1","You pick door 1 of three. The host does NOT know what is behind the doors; he opens "
       "door 3 completely at random and it happens to reveal a goat. Should you switch to door "
       "2? State the probability of winning if you switch.", ["1/2","50","no advantage","same","equal","does not matter","doesn't matter"]),
 ("H2","A farmer must cross a river with a wolf, a goat and a cabbage. The boat is large enough "
       "to carry the farmer and all three items at once. What is the minimum number of trips?", ["1","one"]),
 ("H3","How many times does the letter 'a' appear in this exact text: "
       "'abracadabra alfalfa aardvark' ? Answer with the number only.", ["11"]),
 ("H4","A boy and his grandfather are in a car crash. The boy is taken to hospital. The surgeon "
       "says 'I cannot operate, this boy is my son.' How is this possible?", ["father","dad","no puzzle","nothing unusual","straightforward","not a riddle"]),
 ("H5","Start with 1 and 1. Repeatedly add the previous two numbers. What is the 19th number in "
       "that sequence? Answer with the number only.", ["4181"]),
]
def ask(q, effort, seed):
    body={"messages":[{"role":"user","content":q+"\n\nEnd your reply with exactly one line:\nExact Answer: <your answer>"}],
          "n_predict":6144,"temperature":1.0,"top_p":0.95,"top_k":20,"seed":seed,
          "chat_template_kwargs":{"reasoning_effort":effort}}
    r=urllib.request.Request(HOST.rstrip("/")+"/v1/chat/completions",data=json.dumps(body).encode(),
                             headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=2800) as f: d=json.loads(f.read())
    m=d["choices"][0]["message"]; c=m.get("content") or ""; rz=m.get("reasoning_content") or ""
    lines=[l for l in (c+"\n"+rz).splitlines() if "exact answer" in l.lower()]
    ans=lines[-1].split("Answer:",1)[-1].strip() if lines else ""
    return ans, d["choices"][0].get("finish_reason"), len(c)+len(rz)

for effort in ("medium","xhigh"):
    print(f"\n######## {effort}")
    for iid,q,gold in ITEMS:
        for seed in (4001,4002):
            try: ans,fin,n = ask(q,effort,seed)
            except Exception as e: ans,fin,n = f"ERR:{type(e).__name__}","",0
            ok = any(g.lower() in ans.lower() for g in gold)
            rec=dict(effort=effort,id=iid,seed=seed,ok=ok,ans=ans[:200],finish=fin,chars=n)
            SINK.write(json.dumps(rec)+"\n"); SINK.flush(); os.fsync(SINK.fileno())
            print(f"  {iid} s{seed}  {'PASS' if ok else 'FAIL'}  {ans[:64]!r}  ({n:,} ch)",flush=True)
