#!/usr/bin/env python3
"""PREREG_SCI_DISTILL.md gate: render every GPQA prompt of rounds 1-4 exactly as run_gpqa.py sends it (server's
/apply-template, thinking ON), tokenize it on the same server, and print one sha256 over all token-id lists plus the
render tail. Both arms must print the same line. Prints no item text.
Usage: gpqa_gate.py URL"""
import hashlib, sys
import httpx
from run_gpqa import items, render

url = sys.argv[1]; c = httpx.Client(timeout=120); h = hashlib.sha256(); n = 0; tails = set()
for rnd in range(1, 5):
    for it in items():
        prompt = render(it, rnd)[0]
        p = c.post(f"{url}/apply-template", json={"messages": [{"role": "user", "content": prompt}],
                   "chat_template_kwargs": {"enable_thinking": True}}).json()["prompt"]
        tails.add(p[-40:].split("<|im_end|>")[-1])
        ids = [t if isinstance(t, int) else t["id"] for t in c.post(f"{url}/tokenize", json={"content": p, "add_special": True}).json()["tokens"]]
        h.update((f"{it['id']}:{rnd}:" + ",".join(map(str, ids)) + "\n").encode()); n += 1
print(f"{n} {h.hexdigest()} tails={sorted(tails)!r}")
