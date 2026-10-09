#!/usr/bin/env python3
"""PREREG_KMIC_TRUST_73 client: detbench.py ARM OUT.jsonl -- warmup, 3 seeded reps (seed 1, temp 1.0, 512 tok),
1 greedy (temp 0, 256 tok), all on the 2k slice, cache_prompt false."""
import json, os, sys, time, urllib.request
ARM, OUT = sys.argv[1], sys.argv[2]
URL = "http://127.0.0.1:8087"
IDS = json.load(open(os.path.expanduser("~/kdtrust/corpus_ids.json")))[212992:215040]

def req(path, body=None, timeout=1800):
    data = None if body is None else json.dumps(body).encode()
    return json.loads(urllib.request.urlopen(urllib.request.Request(URL + path, data, {"Content-Type": "application/json"}), timeout=timeout).read())

def write(rec):
    with open(OUT, "a") as f:
        f.write(json.dumps(rec) + "\n"); f.flush(); os.fsync(f.fileno())

def collapse(t):
    run = best = 1
    for a, b in zip(t, t[1:]):
        run = run + 1 if a == b else 1; best = max(best, run)
    return {"longest_run": best if t else 0, "distinct": len(set(t))}

for _ in range(900):
    try:
        if req("/health", timeout=5).get("status") == "ok":
            break
    except Exception:
        pass
    time.sleep(1)
else:
    write({"arm": ARM, "name": "health", "error": "never healthy"}); sys.exit(1)
req("/completion", {"prompt": "The capital of France is", "n_predict": 16, "temperature": 0, "top_k": 1})
SEEDED = {"n_predict": 512, "temperature": 1.0, "top_k": 20, "top_p": 0.95, "min_p": 0.0, "seed": 1}
GREEDY = {"n_predict": 256, "temperature": 0, "top_k": 1}
for name, body in [("s1", SEEDED), ("s2", SEEDED), ("s3", SEEDED), ("g", GREEDY)]:
    t0 = time.time()
    try:
        r = req("/completion", {"prompt": IDS, "ignore_eos": True, "cache_prompt": False, **body}); err = None
    except Exception as e:
        r, err = {}, repr(e)
    c = r.get("content") or ""
    t = r.get("timings") or {}
    write({"arm": ARM, "name": name, "wall_s": round(time.time() - t0, 2), "error": err, "tokens_predicted": r.get("tokens_predicted"),
           "timings": t, "content": c, **collapse(c)})
    print(f"{ARM} {name}: {r.get('tokens_predicted')} tok @ {t.get('predicted_per_second', 0):.2f} t/s, draft {t.get('draft_n')}/{t.get('draft_n_accepted')} acc, err={err}", flush=True)
