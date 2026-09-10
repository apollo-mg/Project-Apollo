#!/usr/bin/env python3
"""Hard probe v2 — novel items, verified golds, and the PARSER THAT WORKS.

v1 failed three ways and all three are fixed here:
  1. crude split("Answer:") grabbed the model DELIBERATING about the format instruction.
     v2 reuses the fixture's rule: prefer `content`, never concatenate reasoning, take the
     LAST match. That is what made tier_cal survive xhigh's verbose traces.
  2. H4 had no unique correct answer ('mother' was consistent, merely unnecessary). Fixed by
     making the memorised answer IMPOSSIBLE — the surgeon is stated to be male.
  3. famous puzzles are contaminated in BOTH directions: the subversion is memorised too, and
     Fibonacci(19)=4181 is likely recalled rather than computed. Every item here is novel, and
     every gold was computed in code.
"""
import json, os, re, sys, urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://10.0.0.194:8081"
SINK = open("hard2_results.jsonl", "a", encoding="utf-8")
ANS = re.compile(r"Exact Answer\s*:\s*(.+?)(?:\n|$)", re.I)

ITEMS = [
 ("N1", "Define a(1)=3, a(2)=7, and for n>=3, a(n) = 2*a(n-1) - a(n-2) + n. What is a(10)?", ["231"]),
 ("N2", "How many times does the two-character string '11' occur in '1111111'? Count overlapping "
        "occurrences.", ["6"]),
 ("N3", "Start with the list [4, 9, 2, 15, 7, 11, 3]. In each round, replace every odd number "
        "with double itself, and every even number with itself divided by 2 (integer division). "
        "After 3 complete rounds, what is the sum of the list?", ["93"]),
 ("N4", "Four people A, B, C, D sit in a row of four seats. A must sit somewhere to the left of "
        "B. C and D must be adjacent. C must not be in the leftmost seat. How many seating "
        "arrangements satisfy all three constraints?", ["5"]),
 ("N5", "How many integers from 1 to 1000 inclusive are divisible by 3 or by 5?", ["467"]),
 ("N6", "A boy and his grandfather are in a car crash. The boy needs surgery. The male surgeon "
        "on duty says 'I cannot operate on him, this boy is my son.' Given the surgeon is male, "
        "who is the surgeon to the boy?", ["father","dad"]),
]

def pick(content, reasoning, fin):
    """Fixture rule: content first, reasoning only as fallback, LAST match wins."""
    for text in (content, reasoning if fin != "length" else ""):
        ms = ANS.findall(text or "")
        if ms: return ms[-1].strip(), len(ms)
    return "", 0

def ask(q, effort, seed):
    body={"messages":[{"role":"user","content":q+"\n\nThink it through, then end your reply with "
          "exactly one line:\nExact Answer: <your answer>"}],
          "n_predict":6144,"temperature":1.0,"top_p":0.95,"top_k":20,"seed":seed,
          "chat_template_kwargs":{"reasoning_effort":effort}}
    r=urllib.request.Request(HOST.rstrip("/")+"/v1/chat/completions",data=json.dumps(body).encode(),
                             headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=2800) as f: d=json.loads(f.read())
    m=d["choices"][0]["message"]; c=m.get("content") or ""; rz=m.get("reasoning_content") or ""
    fin=d["choices"][0].get("finish_reason")
    ans,nm=pick(c,rz,fin)
    return ans,nm,fin,len(c)+len(rz)

for effort in ("medium","xhigh"):
    print(f"\n######## {effort}")
    for iid,q,gold in ITEMS:
        for seed in (5001,5002):
            try: ans,nm,fin,n = ask(q,effort,seed)
            except Exception as e: ans,nm,fin,n = f"ERR:{type(e).__name__}",0,"",0
            ok = any(re.search(rf"\b{re.escape(g)}\b", ans, re.I) for g in gold)
            rec=dict(effort=effort,id=iid,seed=seed,ok=ok,ans=ans[:200],matches=nm,finish=fin,chars=n)
            SINK.write(json.dumps(rec)+"\n"); SINK.flush(); os.fsync(SINK.fileno())
            print(f"  {iid} s{seed}  {'PASS' if ok else 'FAIL'}  {ans[:56]!r}  ({n:,} ch)",flush=True)
