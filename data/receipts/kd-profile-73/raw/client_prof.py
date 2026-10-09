#!/usr/bin/env python3
"""PREREG_KD_PROFILE_73 client: client_prof.py CELL MODE OUT.jsonl (MODE f16: 2k twice; q4: 2k then 32k).
Sleeps 3 s between requests so each request's kernels form their own cluster in the trace."""
import json, os, sys, time, urllib.request
CELL, MODE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
URL = "http://127.0.0.1:8086"
IDS = json.load(open(os.path.expanduser("~/kdprof/corpus_ids.json")))
SL = {"2k": (212992, 215040), "32k": (131072, 163840)}

def req(path, body=None, timeout=3600):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(URL + path, data, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())

def write(rec):
    with open(OUT, "a") as f:
        f.write(json.dumps(rec) + "\n"); f.flush(); os.fsync(f.fileno())

for _ in range(600):
    try:
        if req("/health", timeout=5).get("status") == "ok":
            break
    except Exception:
        pass
    time.sleep(1)
time.sleep(3)
plan = [("warmup", None)] + ([("r1", "2k"), ("r2", "2k")] if MODE == "f16" else [("r2k", "2k"), ("r32k", "32k")])
for name, sl in plan:
    t0 = time.time()
    if sl is None:
        body = {"prompt": "The capital of France is", "n_predict": 16, "temperature": 0, "top_k": 1}
    else:
        a, b = SL[sl]
        body = {"prompt": IDS[a:b], "n_predict": 256, "temperature": 0, "top_k": 1, "ignore_eos": True, "cache_prompt": False}
    try:
        r = req("/completion", body); err = None
    except Exception as e:
        r, err = {}, repr(e)
    write({"cell": CELL, "name": name, "t0": t0, "t1": time.time(), "error": err, "timings": r.get("timings"),
           "tokens_predicted": r.get("tokens_predicted"), "content": r.get("content")})
    t = r.get("timings") or {}
    print(f"{CELL} {name} prompt {t.get('prompt_n')} @ {t.get('prompt_per_second', 0):.1f} t/s, "
          f"decode {t.get('predicted_n')} @ {t.get('predicted_per_second', 0):.2f} t/s err={err}", flush=True)
    time.sleep(3)
