#!/usr/bin/env python3
"""End-to-end test of the wake proxy's pre-warm (modules/wake_proxy.py), against the LIVE proxy on :8099.
  A. capture: a Hermes-shaped chat through the proxy records the head
  B. POST /warm, then a chat with the same head + a new question -> cache_n ~= head tokens
  C. the real path: POST /suspend, then GET /props (a client's startup probe) -> wake + load + automatic warm;
     then a chat -> cache_n ~= head tokens
Writes raw/warm_proxy_e2e.jsonl."""
import json, os, time, urllib.request
from pathlib import Path
P = "http://127.0.0.1:8099"
HERE = Path(__file__).parent
OUT = HERE / "raw" / "warm_proxy_e2e.jsonl"

def call(method, path, body=None, timeout=1800):
    r = urllib.request.Request(P + path, method=method, data=None if body is None else json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read() or b"{}")

def write(rec):
    with open(OUT, "a") as f:
        f.write(json.dumps({"t": time.time(), **rec}) + "\n"); f.flush(); os.fsync(f.fileno())
    print(json.dumps(rec)[:320], flush=True)

corpus = (HERE.parent / "quant-hesitation" / "corpus_reasoning.txt").read_text()
system = ("You are Hermes, a careful local assistant. Operating notes follow.\n\n" + corpus[40000:70000] +
          "\n\nConversation started: Wednesday, September 23, 2026 (America/New_York, EDT, UTC-04:00)")  # yesterday: must be re-dated
tools = [{"type": "function", "function": {"name": f"tool_{i}", "description": f"Synthetic tool {i}.",
          "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}} for i in range(6)]
today = time.strftime("%A, %B %d, %Y")
sys_today = system.replace("Wednesday, September 23, 2026", today)
KW = {"chat_template_kwargs": {"enable_thinking": False}}

def chat(sys_text, q, name):
    t0 = time.time()
    r = call("POST", "/v1/chat/completions", {"messages": [{"role": "system", "content": sys_text},
             {"role": "user", "content": q}], "tools": tools, "max_tokens": 8, "temperature": 0, **KW})
    t = r.get("timings", {})
    write({"step": name, "wall_s": round(time.time() - t0, 2), "cache_n": t.get("cache_n"), "prompt_n": t.get("prompt_n")})

chat(system, "What is this about? One sentence.", "A_capture_chat_yesterday_date")
write({"step": "A_status", "warm": call("GET", "/status")["warm"]})
write({"step": "B_warm", "result": call("POST", "/warm")})
chat(sys_today, "Name one assumption, briefly.", "B_chat_after_warm_today")
write({"step": "C_suspend", "result": call("POST", "/suspend", timeout=120)})
time.sleep(20)
t0 = time.time(); call("GET", "/props", timeout=600)
write({"step": "C_props_woke", "wall_s": round(time.time() - t0, 1)})
for _ in range(120):                                    # the post-load warm runs in the background
    st = call("GET", "/status")["warm"]["last"]
    if st and "post-load" in st.get("reason", ""): break
    time.sleep(5)
write({"step": "C_auto_warm", "result": st})
chat(sys_today, "What does the second section argue? One line.", "C_chat_after_auto_warm")
