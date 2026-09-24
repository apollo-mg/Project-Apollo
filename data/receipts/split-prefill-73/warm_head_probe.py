#!/usr/bin/env python3
"""Can a warm-up reuse a Hermes-shaped head on .73's hybrid model? (feasibility probe for a wake-proxy pre-warm)
Through the wake proxy (:8099, daily config). Synthetic head: ~8k-token system prompt + 6 tool schemas.
  1. cold chat request with head + user A           -> baseline cache_n (expect ~0 on a fresh server)
  2. unrelated request (evicts the slot at -np 1)
  3. warm-up: raw /completion of the rendered head, cut exactly where the user turn starts, n_predict 1
  4. chat request with head + user B (different)      -> cache_n should be ~= the head's token count
Writes raw/warm_head_probe.jsonl."""
import json, os, time, urllib.request
from pathlib import Path
URL = "http://10.0.0.73:8080"   # direct: the wake proxy forwards only /v1, /props, /slots (step 1 ran via :8099)
HERE = Path(__file__).parent
OUT = HERE / "raw" / "warm_head_probe.jsonl"

def req(path, body, timeout=1800):
    r = urllib.request.Request(URL + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read())

def write(rec):
    with open(OUT, "a") as f:
        f.write(json.dumps({"t": time.time(), **rec}) + "\n"); f.flush(); os.fsync(f.fileno())
    print(json.dumps(rec)[:300], flush=True)

corpus = (HERE.parent / "quant-hesitation" / "corpus_reasoning.txt").read_text()
system = "You are Hermes, a careful local assistant. Operating notes follow.\n\n" + corpus[:30000] + \
         "\n\nConversation started: Thursday, September 24, 2026 (America/New_York, EDT, UTC-04:00)"
tools = [{"type": "function", "function": {"name": f"tool_{i}", "description": f"Synthetic tool {i} for the probe.",
          "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}},
                         "required": ["path"]}}} for i in range(6)]
KW = {"chat_template_kwargs": {"enable_thinking": False}}

def chat(user, name):
    t0 = time.time()
    r = req("/v1/chat/completions", {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                                     "tools": tools, "max_tokens": 16, "temperature": 0, **KW})
    t = r.get("timings", {})
    write({"step": name, "wall_s": round(time.time() - t0, 2), "cache_n": t.get("cache_n"), "prompt_n": t.get("prompt_n"),
           "prompt_ms": t.get("prompt_ms")})

import sys
if "--from-2" not in sys.argv:
    chat("In one sentence: what is the first question in the notes?", "1_cold_A")
req("/completion", {"prompt": "Unrelated filler request to evict the slot.", "n_predict": 4, "temperature": 0})
write({"step": "2_evict"})
# render the head exactly as the server would, then cut where the user content begins
MARK = "USER_CONTENT_MARKER_7f3a"
rendered = req("/apply-template", {"messages": [{"role": "system", "content": system}, {"role": "user", "content": MARK}],
                                   "tools": tools, **KW})["prompt"]
head = rendered[:rendered.index(MARK)]
n_head = len(req("/tokenize", {"content": head, "add_special": False, "parse_special": True})["tokens"])
t0 = time.time()
w = req("/completion", {"prompt": head, "n_predict": 1, "temperature": 0, "cache_prompt": True})
write({"step": "3_warm", "head_tokens": n_head, "head_tail": head[-60:], "wall_s": round(time.time() - t0, 2),
       "prompt_n": w.get("timings", {}).get("prompt_n")})
chat("List two assumptions the notes make.", "4_warm_B")
