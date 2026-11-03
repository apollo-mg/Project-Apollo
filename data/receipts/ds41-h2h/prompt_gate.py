#!/usr/bin/env python3
"""PREREG_DS41_H2H.md gate: render every M1 item exactly as run_main.py's R-gen does (server's /apply-template, thinking
off), tokenize it on the same server, and print one sha256 over all token-id lists. Both arms must print the same hash:
equal Jinja text is not equal prompts (metadata decides BOS and special tokens).
Usage: prompt_gate.py URL"""
import hashlib, json, sys
from pathlib import Path
import httpx
QA = Path(__file__).resolve().parent.parent / "quant-abstention"
PROMPT = json.load(open(QA.parent / "viability" / "fixture_v0_beta.json"))["tier_cal"]["prompt"]
url = sys.argv[1]; c = httpx.Client(timeout=120); h = hashlib.sha256(); n = 0
for l in open(QA / "corpus" / "M1.jsonl"):
    it = json.loads(l)
    p = c.post(f"{url}/apply-template", json={"messages": [{"role": "user", "content": PROMPT.format(q=it["question"])}],
               "chat_template_kwargs": {"enable_thinking": False}}).json()["prompt"]
    ids = [t if isinstance(t, int) else t["id"] for t in c.post(f"{url}/tokenize", json={"content": p, "add_special": True}).json()["tokens"]]
    h.update((it["id"] + ":" + ",".join(map(str, ids)) + "\n").encode()); n += 1
print(f"{n} {h.hexdigest()}")
