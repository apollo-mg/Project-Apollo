#!/usr/bin/env python3
"""Media in --resume (buun 1c5e564b "server: support media in resume and VBR host cache") on .73.

One round trip, daily flags + --resume, -np 1, tensor split (resume_test.py's DAILY):
  turn 1   system (~9k tokens, tools) + user [image media_probe.png, "What word and number are written in the image?"]
  SIGTERM  graceful save (timed, store sized)
  restart  --resume (load timed, restore lines logged)
  turn 2   the same conversation + "What colour is the circle, and what colour is the rectangle? Two words."
The image is re-sent in turn 2 (the chat API is stateless); what matters is cache_n vs prompt_n after the restart,
i.e. whether the restored prefix covers the image chunk, and that the answers match the image (HARBOR 4729; red
circle, blue rectangle).
Run once per build: BIN_OVERRIDE=<llama-server> BUILD_TAG=<commit>. Appends raw/resume_media_test.jsonl.
"""
import base64, json, os, subprocess, sys, time, urllib.request
from pathlib import Path
from warm_crash_repro_lib import system, tools, KW

NODE = "http://10.0.0.73:8080"
HERE = Path(__file__).parent
OUT = HERE / "raw" / "resume_media_test.jsonl"
BIN = os.environ["BIN_OVERRIDE"]
TAGB = os.environ.get("BUILD_TAG", "?")
STORE = "/mnt/models/resume-test"
DAILY = ("-m '/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf' --mmproj '/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf' "
         "-ngl 99 -c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 1 -fit off -sm tensor -fa on "
         "--spec-type draft-mtp --draft-max 3 --jinja --kv-unified --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' "
         "--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 0.0 --host 0.0.0.0 --port 8080")
IMG = "data:image/png;base64," + base64.b64encode(open(HERE / "media_probe.png", "rb").read()).decode()


def call(method, path, body=None, timeout=900):
    r = urllib.request.Request(NODE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read() or b"{}")


def ssh(cmd, timeout=700):
    return subprocess.run(["ssh", "10.0.0.73", cmd], capture_output=True, text=True, timeout=timeout).stdout.strip()


def write(rec):
    with open(OUT, "a") as f:
        f.write(json.dumps({"t": time.time(), "build": TAGB, **rec}) + "\n"); f.flush(); os.fsync(f.fileno())
    print(json.dumps(rec)[:400], flush=True)


def alive(pid):
    return ssh(f"kill -0 {pid} 2>/dev/null && echo alive || echo DEAD")


def start(log):
    ssh("pkill -x llama-server; for i in $(seq 120); do pgrep -x llama-server >/dev/null || break; sleep 5; done; "
        "pgrep -x llama-server && kill -9 $(pgrep -x llama-server); sleep 3")
    t0 = time.time()
    ssh(f"mkdir -p ~/split73; setsid nohup {BIN} {DAILY} --resume --resume-path {STORE} > ~/split73/{log}.log 2>&1 "
        f"< /dev/null & echo $! > ~/split73/{log}.pid")
    for _ in range(200):
        try:
            if call("GET", "/health", timeout=5).get("status") == "ok":
                break
        except Exception:
            pass
        time.sleep(2)
    return ssh(f"cat ~/split73/{log}.pid"), round(time.time() - t0, 1)


def chat(m, max_tokens, name):
    t0 = time.time(); err = None; t = {}; reply = ""
    try:
        r = call("POST", "/v1/chat/completions", {"messages": m, "tools": tools, "max_tokens": max_tokens,
                                                  "temperature": 0, **KW})
        t = r.get("timings", {}); reply = r["choices"][0]["message"].get("content") or ""
    except Exception as e:
        err = repr(e)
    write({"step": name, "wall_s": round(time.time() - t0, 2), "cache_n": t.get("cache_n"), "prompt_n": t.get("prompt_n"),
           "prompt_ms": t.get("prompt_ms"), "reply": reply[:200], "error": err})
    return reply


tag = "M" + TAGB[:4]
ssh(f"rm -rf {STORE}; mkdir -p {STORE}")
pid, load_s = start(f"{tag}1")
write({"step": "start1", "load_s": load_s})
u1 = {"role": "user", "content": [{"type": "image_url", "image_url": {"url": IMG}},
                                  {"type": "text", "text": "What word and number are written in the image? Answer briefly."}]}
m1 = [{"role": "system", "content": system}, u1]
reply = chat(m1, 24, "turn1_image")
time.sleep(10)
t0 = time.time(); ssh(f"kill -TERM {pid}")
for _ in range(600):
    if alive(pid) == "DEAD":
        break
    time.sleep(1)
write({"step": "shutdown", "save_s": round(time.time() - t0, 1), "store": ssh(f"du -sh {STORE} | cut -f1"),
       "log": ssh(f"grep -i -E 'resume|save|media|mtmd|GGML_ASSERT' ~/split73/{tag}1.log | tail -8")})
pid, load_s = start(f"{tag}2")
write({"step": "start2", "load_s": load_s, "log": ssh(f"grep -i -E 'resume|restor|media|mtmd' ~/split73/{tag}2.log | tail -8")})
chat(m1 + [{"role": "assistant", "content": reply},
           {"role": "user", "content": "What colour is the circle, and what colour is the rectangle? Two words."}],
     16, "turn2_after_restart")
time.sleep(3)
write({"step": "end", "server": alive(pid),
       "log": ssh(f"grep -i -E 'restor|host|media|mtmd|reuse' ~/split73/{tag}2.log | tail -10")})
