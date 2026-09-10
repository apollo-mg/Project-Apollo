#!/usr/bin/env python3
"""Parallel tool calls and cross-turn state tracking, via the native OpenAI `tools` API.

Four probes, hardest last. Everything goes through /v1/chat/completions with a `tools` array
and is graded on the `tool_calls` field of the response -- not on prose. A model that describes
a tool call instead of emitting one FAILS, which is the distinction that matters for a harness.

P1 single      one call, correct name and arguments
P2 parallel    three independent calls in ONE assistant turn
P3 chained     call -> tool result fed back -> second call USING that result
P4 state       four turns, running list; must report what it has accumulated
"""
import json, sys, urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8086"
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 3

WEATHER = {"type":"function","function":{"name":"get_weather","description":"Current weather for a city.",
    "parameters":{"type":"object","properties":{"city":{"type":"string"},"units":{"type":"string","enum":["celsius","fahrenheit"]}},"required":["city","units"]}}}
ADDITEM = {"type":"function","function":{"name":"add_item","description":"Append an item to the shopping list.",
    "parameters":{"type":"object","properties":{"item":{"type":"string"}},"required":["item"]}}}
LISTALL = {"type":"function","function":{"name":"list_items","description":"Return every item on the shopping list.",
    "parameters":{"type":"object","properties":{},"required":[]}}}

def chat(messages, tools, max_tokens=2048, temp=1.0, seed=None):
    body={"messages":messages,"tools":tools,"tool_choice":"auto","max_tokens":max_tokens,
          "temperature":temp,"top_p":0.95,"top_k":20}
    if seed is not None: body["seed"]=seed
    req=urllib.request.Request(HOST.rstrip("/")+"/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d=json.loads(r.read())
    m=d["choices"][0]["message"]
    return m, d["choices"][0].get("finish_reason","")

def calls_of(m):
    out=[]
    for c in (m.get("tool_calls") or []):
        f=c.get("function",{})
        try: args=json.loads(f.get("arguments") or "{}")
        except Exception: args={"_unparseable": f.get("arguments")}
        out.append((f.get("name"), args))
    return out

def p1(seed):
    m,_=chat([{"role":"user","content":"What's the weather in Paris in celsius?"}],[WEATHER],seed=seed)
    c=calls_of(m)
    ok = len(c)==1 and c[0][0]=="get_weather" and c[0][1].get("city","").lower()=="paris" and c[0][1].get("units")=="celsius"
    return ok, f"{len(c)} call(s): {c}"

def p2(seed):
    m,_=chat([{"role":"user","content":"Get the weather in celsius for Paris, Tokyo and Cairo. Make all three calls now."}],[WEATHER],seed=seed)
    c=calls_of(m)
    cities={str(a.get("city","")).lower() for n,a in c if n=="get_weather"}
    ok = len(c)==3 and cities=={"paris","tokyo","cairo"} and all(a.get("units")=="celsius" for _,a in c)
    return ok, f"{len(c)} call(s), cities={sorted(cities)}"

def p3(seed):
    msgs=[{"role":"user","content":"Check the weather in Paris in celsius. Then, if it is above 10 degrees, also check Oslo in celsius. Do the first call now."}]
    m,_=chat(msgs,[WEATHER],seed=seed)
    c1=calls_of(m)
    if len(c1)!=1 or c1[0][0]!="get_weather":
        return False, f"turn1 wrong: {c1}"
    tcid=(m.get("tool_calls") or [{}])[0].get("id") or "call_1"
    msgs.append({"role":"assistant","tool_calls":m.get("tool_calls")})
    msgs.append({"role":"tool","tool_call_id":tcid,"name":"get_weather",
                 "content":json.dumps({"city":"Paris","units":"celsius","temp":18})})
    m2,_=chat(msgs,[WEATHER],seed=seed)
    c2=calls_of(m2)
    ok = len(c2)==1 and c2[0][0]=="get_weather" and str(c2[0][1].get("city","")).lower()=="oslo"
    return ok, f"turn1={c1[0][1]} turn2={c2}"

def p4(seed):
    msgs=[]; tools=[ADDITEM,LISTALL]; added=[]
    for item in ("milk","bread","eggs"):
        msgs.append({"role":"user","content":f"Add {item} to my shopping list."})
        m,_=chat(msgs,tools,seed=seed)
        c=calls_of(m)
        if len(c)!=1 or c[0][0]!="add_item":
            return False, f"add {item} -> {c}"
        added.append(str(c[0][1].get("item","")).lower())
        tcid=(m.get("tool_calls") or [{}])[0].get("id") or f"call_{item}"
        msgs.append({"role":"assistant","tool_calls":m.get("tool_calls")})
        msgs.append({"role":"tool","tool_call_id":tcid,"name":"add_item","content":json.dumps({"ok":True,"item":item})})
    msgs.append({"role":"user","content":"What is on my list? Use the tool to check."})
    m,_=chat(msgs,tools,seed=seed)
    c=calls_of(m)
    ok = any(n=="list_items" for n,_ in c) and added==["milk","bread","eggs"]
    return ok, f"added={added} final_call={[n for n,_ in c]}"

PROBES=[("P1 single",p1),("P2 parallel",p2),("P3 chained",p3),("P4 state",p4)]
print(f"### tool probe  host={HOST}  reps={REPS}")
tot={}
for name,fn in PROBES:
    res=[]
    for r in range(REPS):
        try: ok,detail=fn(1000+r)
        except Exception as e: ok,detail=False,f"EXC {type(e).__name__}: {str(e)[:90]}"
        res.append(ok); print(f"  {name:12s} rep{r+1}  {'PASS' if ok else 'FAIL'}  {detail[:118]}")
    tot[name]=sum(res)
    print(f"  {name:12s} -> {sum(res)}/{REPS}\n")
print("### SUMMARY")
for k,v in tot.items(): print(f"  {k:12s} {v}/{REPS}")
