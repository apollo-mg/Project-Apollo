#!/usr/bin/env python3
"""MTP on/off throughput A/B via llama-server. llama-bench cannot do this — it has
no --spec-type — so speed is measured from real completions.

Reported claim under test: Jabba and eric independently see MTP making Qwen 3.8
SLOWER. Jabba has reported this before on other models, so it may be specific to
his hardware; that is what an independent fleet measurement is for.

Speculative decoding is content-dependent by construction — throughput depends on
draft acceptance, which depends on how predictable the text is. So this uses a
prompt mix, reports per-prompt as well as aggregate, and ALTERNATES arms rather
than running all-on then all-off (this fleet has produced 2-3.9x position
artifacts on identical configs).
"""
import json, os, statistics, sys, time, urllib.request

HOST = os.environ.get("HOST", "http://127.0.0.1:8082")
PROMPTS = [
    ("code",    "Write a Python class LRUCache with get and put, O(1) both. Include docstrings."),
    ("prose",   "Explain how a CPU branch predictor works, in three paragraphs."),
    ("list",    "List the first 30 prime numbers, comma separated."),
    ("repeat",  "Write the numbers 1 to 60, one per line, with no other text."),
    ("reason",  "A tank fills at 4 L/min and drains at 1.5 L/min. It starts at 20 L and holds 200 L. How long until full? Show your work."),
]

def gen(prompt, n_predict=320, timeout=600):
    body = {"messages":[{"role":"user","content":prompt}], "temperature":0, "top_k":1,
            "seed":1234, "n_predict":n_predict}
    req = urllib.request.Request(f"{HOST}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    t0=time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r: d=json.load(r)
    dt=time.time()-t0
    u=d.get("usage",{})
    tok=u.get("completion_tokens") or 0
    return {"tok":tok, "s":round(dt,2), "tps":round(tok/dt,2) if dt>0 else 0,
            "finish":d["choices"][0].get("finish_reason"),
            # llama.cpp returns reasoning in a SEPARATE field. Reading only
            # `content` made an earlier run report "outputs identical" when both
            # arms had put every token in the think block and content was empty.
            # Throughput was never affected (completion_tokens counts both), but
            # any text comparison without this is vacuous.
            "reasoning":d["choices"][0]["message"].get("reasoning_content") or "",
            "text":d["choices"][0]["message"].get("content") or ""}

def main():
    tag=sys.argv[1] if len(sys.argv)>1 else "arm"
    reps=int(os.environ.get("REPS","3"))
    out=[]
    for rep in range(reps):
        for name,p in PROMPTS:
            r=gen(p); r.update(prompt=name, rep=rep, arm=tag)
            out.append(r)
            print(f"  {tag:8s} rep{rep} {name:7s} {r['tok']:>4} tok  {r['s']:>6.2f}s  "
                  f"{r['tps']:>6.2f} t/s  {r['finish']}  "
                  f"c={len(r['text'])} rc={len(r['reasoning'])}", flush=True)
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)), f"mtp_{tag}.json")
    json.dump(out, open(path,"w"), indent=1)
    tps=[r["tps"] for r in out if r["tok"]>0]
    print(f"\n=== {tag}: median {statistics.median(tps):.2f} t/s  "
          f"mean {statistics.mean(tps):.2f}  n={len(tps)} ===")
    for name,_ in PROMPTS:
        v=[r["tps"] for r in out if r["prompt"]==name]
        print(f"   {name:8s} median {statistics.median(v):>6.2f} t/s   {[f'{x:.1f}' for x in v]}")
    print(f"-> {path}")

main()
