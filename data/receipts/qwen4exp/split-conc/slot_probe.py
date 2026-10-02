#!/usr/bin/env python3
"""PREREG_NUMA_PREFILL.md Deviation 1: two parallel 256-token /completion requests pinned to a slot pair via id_slot.
usage: slot_probe.py URL CFG OUT"""
import concurrent.futures as cf, itertools, json, os, sys, time, urllib.request

URL, CFG, OUT = sys.argv[1:4]
P = ["Explain how a heat pump works, in about 250 words.\n\n", "Write a 250-word story about a lighthouse keeper.\n\n"]


def go(slot, i):
    body = {"prompt": P[i], "n_predict": 256, "temperature": 0, "seed": 1, "cache_prompt": False, "id_slot": slot,
            "ignore_eos": True}
    r = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/completion", json.dumps(body).encode(),
                                                                {"content-type": "application/json"}), timeout=900))
    return {"slot": slot, "id_slot_reported": r.get("id_slot"), **(r.get("timings") or {})}


with open(OUT, "a") as f:
    for rep in (1, 2):
        for a, b in [(0, 1), (1, 2), (2, 3), (0, 2), (1, 3), (0, 3)]:
            t0 = time.time()
            with cf.ThreadPoolExecutor(2) as ex:
                res = list(ex.map(lambda x: go(*x), [(a, 0), (b, 1)]))
            row = {"cfg": CFG, "rep": rep, "pair": [a, b], "wall_s": round(time.time() - t0, 2),
                   "per_stream": [round(r.get("predicted_per_second") or 0, 2) for r in res],
                   "slots_reported": [r["id_slot_reported"] for r in res], "n": [r.get("predicted_n") for r in res]}
            f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno()); print(json.dumps(row), flush=True)
