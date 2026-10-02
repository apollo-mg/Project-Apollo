#!/usr/bin/env python3
"""PREREG_NUMA_PREFILL.md Part P: exact-length cold prefill. Tokenizes wikitext-2 test once via the server, then sends
token-id prompts of 2,048 and 8,192 tokens (3 reps, different offsets) to /completion with n_predict 1 and
cache_prompt false, after one 64-token warm-up. One row per request. usage: pf_probe.py URL CELL OUT TEXTFILE"""
import json, os, sys, time, urllib.request

URL, CELL, OUT, TEXT = sys.argv[1:5]


def post(path, body, timeout=1800):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


ids = post("/tokenize", {"content": open(TEXT, encoding="utf-8").read()[:400000]})["tokens"]
assert len(ids) > 3 * 20000 + 8192, len(ids)
post("/completion", {"prompt": ids[:64], "n_predict": 1, "cache_prompt": False})          # warm-up, not recorded
with open(OUT, "a") as f:
    for n in (2048, 8192):
        for rep in (1, 2, 3):
            off = rep * 20000
            t0 = time.time()
            r = post("/completion", {"prompt": ids[off:off + n], "n_predict": 1, "cache_prompt": False, "temperature": 0})
            tm = r.get("timings") or {}
            row = {"cell": CELL, "n": n, "rep": rep, "prompt_n": tm.get("prompt_n"), "prompt_ms": tm.get("prompt_ms"),
                   "pps": tm.get("prompt_per_second"), "wall_s": round(time.time() - t0, 2)}
            f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
            print(json.dumps(row), flush=True)
