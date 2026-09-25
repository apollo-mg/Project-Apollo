#!/usr/bin/env python3
"""Repro for the llama-server abort after a fresh-server warm-up (ggml-backend-meta.cpp:1783
GGML_ASSERT(size % row_stride == 0), via try_automatic_vbr_restore -> ensure_vbr_replacement_recovery).
Each variant: stop llama-server, reload it through the proxy's /props (auto-warm is off), warm the head directly on
the node, then send a chat that extends the head. Records whether the server survived.
  V1  warm n_predict 1, chat immediately          (the sequence that crashed at 20:11)
  V2  warm n_predict 1, wait 30 s, then chat      (does the idle capture publishing first avoid it?)
  V3  warm n_predict 0, chat immediately          (no generated token to rewind)
  V4  warm n_predict 0, wait 30 s, then chat      (added after V2 crashed and V3 did not wait)
Writes raw/warm_crash_repro.jsonl."""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path
PROXY, NODE = "http://127.0.0.1:8099", "http://10.0.0.73:8080"
HERE = Path(__file__).parent
OUT = HERE / "raw" / "warm_crash_repro.jsonl"

def call(base, method, path, body=None, timeout=900):
    r = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read() or b"{}")

def ssh(cmd):
    return subprocess.run(["ssh", "10.0.0.73", cmd], capture_output=True, text=True, timeout=120).stdout.strip()

def write(rec):
    with open(OUT, "a") as f:
        f.write(json.dumps({"t": time.time(), **rec}) + "\n"); f.flush(); os.fsync(f.fileno())
    print(json.dumps(rec)[:300], flush=True)

corpus = (HERE.parent / "quant-hesitation" / "corpus_reasoning.txt").read_text()
system = ("You are Hermes, a careful local assistant. Operating notes follow.\n\n" + corpus[80000:110000] +
          "\n\nConversation started: " + time.strftime("%A, %B %d, %Y") + " (America/New_York, EDT, UTC-04:00)")
tools = [{"type": "function", "function": {"name": f"tool_{i}", "description": f"Synthetic tool {i}.",
          "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}} for i in range(6)]
KW = {"chat_template_kwargs": {"enable_thinking": False}}
MARK = "USER_CONTENT_MARKER_7f3a"

for name, n_predict, wait in [("V1", 1, 0), ("V2", 1, 30), ("V3", 0, 0), ("V4", 0, 30)]:
    if len(sys.argv) > 1 and name not in sys.argv[1:]:
        continue
    ssh("pkill -x llama-server; sleep 5")
    t0 = time.time(); call(PROXY, "GET", "/props")                       # proxy relaunches the daily config
    load_s = round(time.time() - t0, 1)
    pid = ssh("pgrep -x llama-server")
    rendered = call(NODE, "POST", "/apply-template", {"messages": [{"role": "system", "content": system},
                    {"role": "user", "content": MARK}], "tools": tools, **KW})["prompt"]
    head = rendered[:rendered.index(MARK)]
    w = call(NODE, "POST", "/completion", {"prompt": head, "n_predict": n_predict, "temperature": 0, "cache_prompt": True})
    time.sleep(wait)
    err, t = None, {}
    try:
        r = call(NODE, "POST", "/v1/chat/completions", {"messages": [{"role": "system", "content": system},
                 {"role": "user", "content": "Name one claim it makes, briefly."}], "tools": tools,
                 "max_tokens": 8, "temperature": 0, **KW})
        t = r.get("timings", {})
    except Exception as e:
        err = repr(e)
    time.sleep(3)
    alive = ssh(f"kill -0 {pid} 2>/dev/null && echo alive || echo DEAD")
    assert_line = ssh("grep -m1 GGML_ASSERT ~/wake_proxy_server.log") if alive == "DEAD" else ""
    write({"variant": name, "n_predict": n_predict, "wait_s": wait, "load_s": load_s,
           "warm_prompt_n": w.get("timings", {}).get("prompt_n"), "chat_cache_n": t.get("cache_n"),
           "chat_prompt_n": t.get("prompt_n"), "chat_error": err, "server": alive, "assert": assert_line})
    if alive == "DEAD":
        ssh(f"cp ~/wake_proxy_server.log ~/crash_prewarm_{name}.log")
