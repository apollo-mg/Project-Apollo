#!/usr/bin/env python3
"""Measure the endpoint's run-to-run logprob spread so the canary tolerance is derived, not guessed.
Known context: temp-0 on .73 is not reproducible (agent-benchmark-determinism). The question is
whether the drift is small relative to the gold-vs-emitted differences P-HEAL will compare.
"""
import json, urllib.request, statistics as st
B = "http://127.0.0.1:8092"
S = "Answer factual questions directly and concisely. If you don't know, say 'I don't know'."
def post(p, d):
    r = urllib.request.Request(B+p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=120).read().decode())
tpl = post("/apply-template", {"messages":[{"role":"system","content":S},
           {"role":"user","content":"What is the capital of France?"}],
           "chat_template_kwargs":{"enable_thinking":False}})["prompt"]
vals, toks = [], set()
for i in range(12):
    d = post("/completion", {"prompt": tpl, "n_predict":1, "n_probs":5, "temperature":0, "cache_prompt":True})
    e = d["completion_probabilities"][0]
    ent = (e.get("top_logprobs") or e.get("probs"))[0]
    toks.add(ent["token"]); vals.append(ent["logprob"])
print(f"top-1 token(s) across 12 reads: {toks}")
print(f"logprob  min={min(vals):.5f} max={max(vals):.5f} spread={max(vals)-min(vals):.5f} "
      f"stdev={st.pstdev(vals):.5f}")
print(f"values: {[round(v,4) for v in vals]}")
