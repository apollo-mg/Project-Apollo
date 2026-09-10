#!/usr/bin/env python3
"""Adversarial follow-up. The first probe scored 12/12 on cases where calling a tool is always
correct -- which cannot distinguish a model that reasons from one that always calls.

P6 is the control that P3 lacked: same chained setup, but the returned temperature is BELOW the
threshold, so the correct behaviour is NOT to call again. A model that passed P3 by reflex
fails here.

P5 no-tool     question needs no tool; calling one is the failure
P6 cond-false  temp 5 < 10 -> must NOT call Oslo   [control for P3]
P7 missing-arg city unspecified; must ask, not invent one
P8 no-fit      request no offered tool covers; must not force one
"""
import json, sys, urllib.request
HOST = sys.argv[1] if len(sys.argv)>1 else "http://127.0.0.1:8086"
REPS = int(sys.argv[2]) if len(sys.argv)>2 else 3
WEATHER={"type":"function","function":{"name":"get_weather","description":"Current weather for a city.",
  "parameters":{"type":"object","properties":{"city":{"type":"string"},"units":{"type":"string","enum":["celsius","fahrenheit"]}},"required":["city","units"]}}}
STOCK={"type":"function","function":{"name":"get_stock","description":"Current share price for a ticker.",
  "parameters":{"type":"object","properties":{"ticker":{"type":"string"}},"required":["ticker"]}}}
def chat(msgs,tools,seed=None,max_tokens=2048):
    b={"messages":msgs,"tools":tools,"tool_choice":"auto","max_tokens":max_tokens,
       "temperature":1.0,"top_p":0.95,"top_k":20}
    if seed is not None: b["seed"]=seed
    r=urllib.request.Request(HOST.rstrip("/")+"/v1/chat/completions",data=json.dumps(b).encode(),
        headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=300) as f: d=json.loads(f.read())
    return d["choices"][0]["message"]
def calls(m):
    out=[]
    for c in (m.get("tool_calls") or []):
        fn=c.get("function",{})
        try: a=json.loads(fn.get("arguments") or "{}")
        except Exception: a={}
        out.append((fn.get("name"),a))
    return out
def p5(seed):
    m=chat([{"role":"user","content":"What is 17 multiplied by 3? Answer directly."}],[WEATHER,STOCK],seed=seed)
    c=calls(m); txt=(m.get("content") or "")
    return (len(c)==0 and "51" in txt), f"calls={[n for n,_ in c]} content={txt.strip()[:60]!r}"
def p6(seed):
    msgs=[{"role":"user","content":"Check the weather in Paris in celsius. Then, if it is above 10 degrees, also check Oslo in celsius. Do the first call now."}]
    m=chat(msgs,[WEATHER],seed=seed); c1=calls(m)
    if len(c1)!=1: return False, f"turn1 wrong: {c1}"
    tid=(m.get("tool_calls") or [{}])[0].get("id") or "c1"
    msgs+= [{"role":"assistant","tool_calls":m.get("tool_calls")},
            {"role":"tool","tool_call_id":tid,"name":"get_weather",
             "content":json.dumps({"city":"Paris","units":"celsius","temp":5})}]
    m2=chat(msgs,[WEATHER],seed=seed); c2=calls(m2)
    oslo=[n for n,a in c2 if str(a.get("city","")).lower()=="oslo"]
    return (len(oslo)==0), f"temp=5 -> turn2 calls={[(n,a.get('city')) for n,a in c2]}"
def p7(seed):
    m=chat([{"role":"user","content":"What's the weather like? Use celsius."}],[WEATHER],seed=seed)
    c=calls(m); txt=(m.get("content") or "")
    invented=[a.get("city") for n,a in c if n=="get_weather"]
    return (len(c)==0 and len(txt.strip())>0), f"calls={invented} content={txt.strip()[:70]!r}"
def p8(seed):
    m=chat([{"role":"user","content":"Book me a table for two at 8pm tonight."}],[WEATHER,STOCK],seed=seed)
    c=calls(m); txt=(m.get("content") or "")
    return (len(c)==0 and len(txt.strip())>0), f"calls={[n for n,_ in c]} content={txt.strip()[:70]!r}"
P=[("P5 no-tool",p5),("P6 cond-false",p6),("P7 missing-arg",p7),("P8 no-fit",p8)]
print(f"### adversarial tool probe  host={HOST} reps={REPS}")
tot={}
for name,fn in P:
    r=[]
    for i in range(REPS):
        try: ok,d=fn(1000+i)
        except Exception as e: ok,d=False,f"EXC {type(e).__name__}: {str(e)[:80]}"
        r.append(ok); print(f"  {name:15s} rep{i+1} {'PASS' if ok else 'FAIL'}  {d[:112]}")
    tot[name]=sum(r); print(f"  {name:15s} -> {sum(r)}/{REPS}\n")
print("### SUMMARY"); [print(f"  {k:15s} {v}/{REPS}") for k,v in tot.items()]
