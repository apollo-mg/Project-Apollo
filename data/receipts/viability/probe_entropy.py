#!/usr/bin/env python3
"""Why does temp=1.0 behave like greedy on this model?

Hypothesis: Qwen3.8's next-token distribution is so PEAKED that temperature 1.0 is
already near-deterministic — sampling only ever picks between tokens that don't change
the answer. If true, 'temp 1.0 is the recommended setting' is not a claim about better
sampling; it is a claim that the model no longer needs its distribution sharpened.

Measures the real distribution: top-1 probability and entropy per generated token, at
temp 1.0, across prompt types. Uses a spare slot on the running np=4 server.
"""
import json, math, sys, urllib.request, collections

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://10.0.0.194:8080"
PROMPTS = [
    ("factual-easy",  "What is the capital of France? Answer in one word."),
    ("factual-hard",  "What is the atomic number of tungsten? Answer with the number only."),
    ("false-premise", "In which year did Dmitri Mendeleev win the Nobel Prize in Chemistry?"),
    ("open-ended",    "Write two sentences about why distributed systems are hard."),
    ("arithmetic",    "What is 17 multiplied by 23? Answer with the number only."),
]

def probe(prompt, n=120, temp=1.0):
    body = {"messages": [{"role": "user", "content": prompt}], "n_predict": n,
            "temperature": temp, "top_p": 0.95, "top_k": 20, "logprobs": True,
            "top_logprobs": 5, "chat_template_kwargs": {"reasoning_effort": "medium"}}
    req = urllib.request.Request(HOST.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    return (d["choices"][0].get("logprobs") or {}).get("content") or []

def stats(toks):
    """top-1 prob, and entropy over the returned top-5 (a LOWER BOUND on true entropy)."""
    p1, ent = [], []
    for t in toks:
        tl = t.get("top_logprobs") or []
        if not tl: continue
        ps = [math.exp(x["logprob"]) for x in tl]
        p1.append(max(ps))
        ent.append(-sum(p * math.log2(p) for p in ps if p > 0))
    return p1, ent

print(f"Next-token distribution at temp=1.0 / top_p=0.95 / top_k=20  ({HOST})")
print("entropy is over the returned top-5 only => a LOWER BOUND on the true value\n")
print(f"  {'prompt type':<15}{'tokens':>7}{'median p(top1)':>16}{'mean p(top1)':>14}"
      f"{'median H':>10}{'p1>0.9':>8}{'p1>0.99':>9}")
print("  " + "-"*79)
for name, p in PROMPTS:
    try:
        toks = probe(p)
    except Exception as e:
        print(f"  {name:<15} ERROR {type(e).__name__}"); continue
    p1, ent = stats(toks)
    if not p1: print(f"  {name:<15} no logprobs returned"); continue
    p1s = sorted(p1); med = p1s[len(p1s)//2]
    ents = sorted(ent); mede = ents[len(ents)//2]
    print(f"  {name:<15}{len(p1):>7}{med:>16.4f}{sum(p1)/len(p1):>14.4f}"
          f"{mede:>10.3f}{sum(1 for x in p1 if x>0.9)/len(p1):>8.0%}"
          f"{sum(1 for x in p1 if x>0.99)/len(p1):>9.0%}", flush=True)
