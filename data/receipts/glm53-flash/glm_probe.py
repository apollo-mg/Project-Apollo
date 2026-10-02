#!/usr/bin/env python3
"""PREREG_GLM_NUMA.md: 3 fixed prompts x 2 passes, 256 tokens, reasoning_effort low, temp 0, no prompt cache.
usage: glm_probe.py URL ARM OUT"""
import json, os, sys, time, urllib.request

URL, ARM, OUT = sys.argv[1:4]
P = ["Explain how a heat pump works, in about 200 words.", "Write a short story about a lighthouse keeper.",
     "What is the SI unit of magnetic flux, and how is it defined?"]
with open(OUT, "a") as f:
    for ps in (1, 2):
        for i, p in enumerate(P):
            body = {"messages": [{"role": "user", "content": p}], "max_tokens": 256, "temperature": 0, "seed": 1,
                    "cache_prompt": False, "chat_template_kwargs": {"reasoning_effort": "low"}}
            t0 = time.time()
            r = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/v1/chat/completions", json.dumps(body).encode(),
                                                                        {"content-type": "application/json"}), timeout=1800))
            tm = r.get("timings") or {}
            row = {"arm": ARM, "pass": ps, "prompt": i, "wall_s": round(time.time() - t0, 2), "tps": tm.get("predicted_per_second"),
                   "pp_tps": tm.get("prompt_per_second"), "n": tm.get("predicted_n")}
            f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno()); print(json.dumps(row), flush=True)
