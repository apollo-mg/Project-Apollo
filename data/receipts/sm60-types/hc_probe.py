#!/usr/bin/env python3
"""PREREG_HC_Q8.md: the 6 fixed speed prompts of qwen4exp/run_mtp_clock.py x 2, temp 0, thinking off, 384 tokens,
cache_prompt false. Saves timings AND content (for greedy agreement). usage: hc_probe.py URL ARM OUT"""
import json, os, sys, time, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "qwen4exp"))
from run_mtp_clock import PROMPTS  # noqa: E402

url, arm, out = sys.argv[1:4]
with open(out, "a") as f:
    for rep in (1, 2):
        for pid, p in PROMPTS:
            body = {"messages": [{"role": "user", "content": p}], "max_tokens": 384, "temperature": 0, "seed": 1,
                    "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
            t0 = time.time()
            r = json.load(urllib.request.urlopen(urllib.request.Request(url + "/v1/chat/completions", json.dumps(body).encode(),
                                                                        {"content-type": "application/json"}), timeout=900))
            tm = r.get("timings") or {}
            row = {"arm": arm, "rep": rep, "prompt": pid, "wall_s": round(time.time() - t0, 3),
                   "predicted_n": tm.get("predicted_n"), "predicted_per_second": tm.get("predicted_per_second"),
                   "content": r["choices"][0]["message"].get("content")}
            f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
            print(f"{arm} rep{rep} {pid:8s} {row['predicted_per_second'] or 0:6.2f} tok/s", flush=True)
