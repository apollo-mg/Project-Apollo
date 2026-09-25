#!/usr/bin/env python3
"""The automatic path of the wake proxy's pre-warm: a load triggered by a client's startup probe (/props) should warm
the captured head without being asked. Node stays awake; only llama-server is stopped (pkill -x, exact name).
Appends to raw/warm_proxy_e2e.jsonl. Removes the synthetic head afterwards."""
import json, os, subprocess, time, urllib.request
from pathlib import Path
P = "http://127.0.0.1:8099"
HERE = Path(__file__).parent
OUT = HERE / "raw" / "warm_proxy_e2e.jsonl"
HEAD = Path("/mnt/TG_2TB/Projects/Apollo/run/warm_head.json")

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
system = ("You are Hermes, a careful local assistant. Operating notes follow.\n\n" + corpus[80000:110000] +
          "\n\nConversation started: " + time.strftime("%A, %B %d, %Y") + " (America/New_York, EDT, UTC-04:00)")
tools = [{"type": "function", "function": {"name": f"tool_{i}", "description": f"Synthetic tool {i}.",
          "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}} for i in range(6)]
KW = {"chat_template_kwargs": {"enable_thinking": False}}

def chat(q, name):
    t0 = time.time()
    r = call("POST", "/v1/chat/completions", {"messages": [{"role": "system", "content": system},
             {"role": "user", "content": q}], "tools": tools, "max_tokens": 8, "temperature": 0, **KW})
    t = r.get("timings", {})
    write({"step": name, "wall_s": round(time.time() - t0, 2), "cache_n": t.get("cache_n"), "prompt_n": t.get("prompt_n")})

try:
    chat("One sentence: what is this about?", "D_capture")
    rc = subprocess.run(["ssh", "10.0.0.73", "pkill -x llama-server; sleep 5; pgrep -x llama-server || echo stopped"],
                        capture_output=True, text=True, timeout=60).stdout.strip()
    write({"step": "D_server_stopped", "ssh": rc})
    t0 = time.time(); call("GET", "/props", timeout=900)
    write({"step": "D_props_loaded", "wall_s": round(time.time() - t0, 1)})
    st = {}
    for _ in range(120):
        st = call("GET", "/status")["warm"]["last"] or {}
        if "post-load" in st.get("reason", ""): break
        time.sleep(5)
    write({"step": "D_auto_warm", "result": st})
    chat("Name one claim it makes, briefly.", "D_chat_after_auto_warm")
finally:
    HEAD.unlink(missing_ok=True)
    write({"step": "D_cleanup", "head_removed": not HEAD.exists()})
