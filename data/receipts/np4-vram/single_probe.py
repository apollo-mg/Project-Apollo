#!/usr/bin/env python3
"""Single-stream decode speed and MTP acceptance on .73, 3 prompts x 768 tokens, two passes (pass 2 = cached rows).
usage: single_probe.py LABEL -> appends to single.jsonl"""
import json, os, sys, urllib.request
from pathlib import Path
OUT = Path(__file__).resolve().parent / "single.jsonl"
P = ["Write a detailed 700-word essay on the history of the printing press.",
     "Explain, step by step and in depth, how TCP congestion control works.",
     "Write a Python module implementing an LRU cache with tests and docstrings."]
for rep in (1, 2):
    for i, p in enumerate(P):
        body = json.dumps({"messages": [{"role": "user", "content": p}], "max_tokens": 768, "temperature": 0, "seed": 1,
                           "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}).encode()
        tm = json.load(urllib.request.urlopen(urllib.request.Request("http://10.0.0.73:8080/v1/chat/completions", body,
                                                                     {"content-type": "application/json"}), timeout=900)).get("timings", {})
        row = {"label": sys.argv[1], "rep": rep, "prompt": i, "tps": tm.get("predicted_per_second"), "n": tm.get("predicted_n"),
               "draft_n": tm.get("draft_n"), "acc": tm.get("draft_n_accepted")}
        open(OUT, "a").write(json.dumps(row) + "\n")
        print(row, flush=True)
