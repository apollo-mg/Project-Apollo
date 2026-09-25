#!/usr/bin/env python3
"""buun 2acf5b10f on .73 (worktree ~/buun-resume, build_sm60_resume): two questions.
  A  does the -np 1 idle-reuse abort (INCIDENT_73_NP1_IDLE_REUSE_ABORT, V5) still fire on this build?
  R  --resume round trip: chat turn 1, graceful SIGTERM (time the save, size the store), restart (time the load +
     restore), then turn 2 extending turn 1 -> how much is reused after a restart?
Daily flags throughout. Server launched directly over ssh; the wake proxy sees it as serving.
Appends raw/resume_test.jsonl."""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path
from warm_crash_repro_lib import system, tools, KW
NODE = "http://10.0.0.73:8080"
HERE = Path(__file__).parent
OUT = HERE / "raw" / "resume_test.jsonl"
BIN = "~/buun-resume/build_sm60_resume/bin/llama-server"
STORE = "/mnt/models/resume-test"
DAILY = ("-m '/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf' --mmproj '/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf' "
         "-ngl 99 -c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 1 -fit off -sm tensor -fa on "
         "--spec-type draft-mtp --draft-max 3 --jinja --kv-unified --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' "
         "--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 0.0 --host 0.0.0.0 --port 8080")

def call(method, path, body=None, timeout=900):
    r = urllib.request.Request(NODE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read() or b"{}")

def ssh(cmd, timeout=300):
    return subprocess.run(["ssh", "10.0.0.73", cmd], capture_output=True, text=True, timeout=timeout).stdout.strip()

def write(rec):
    with open(OUT, "a") as f:
        f.write(json.dumps({"t": time.time(), **rec}) + "\n"); f.flush(); os.fsync(f.fileno())
    print(json.dumps(rec)[:360], flush=True)

def start(extra, log):
    # a --resume shutdown can take minutes (save, or a crash plus backtrace): wait for the old server to be GONE,
    # or the new one fails to bind :8080 (observed 00:17)
    ssh("pkill -x llama-server; for i in $(seq 120); do pgrep -x llama-server >/dev/null || break; sleep 5; done; pgrep -x llama-server && kill -9 $(pgrep -x llama-server); sleep 3", timeout=700)
    t0 = time.time()
    ssh(f"mkdir -p ~/split73; setsid nohup {BIN} {DAILY} {extra} > ~/split73/{log}.log 2>&1 < /dev/null & echo $! > ~/split73/{log}.pid")
    for _ in range(200):
        try:
            if call("GET", "/health", timeout=5).get("status") == "ok": break
        except Exception: pass
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
           "prompt_ms": t.get("prompt_ms"), "error": err})
    return reply

def alive(pid):
    return ssh(f"kill -0 {pid} 2>/dev/null && echo alive || echo DEAD")

m1 = [{"role": "system", "content": system}, {"role": "user", "content": "Name one claim it makes, briefly."}]
q2 = {"role": "user", "content": "Why might that be wrong? One line."}

if "A" in sys.argv[1:]:
    pid, load_s = start("", "RA")
    reply = chat(m1, 24, "A_turn1")
    time.sleep(30)
    chat(m1 + [{"role": "assistant", "content": reply}, q2], 16, "A_turn2_after_30s")
    time.sleep(3)
    st = alive(pid)
    write({"step": "A_result", "load_s": load_s, "server": st,
           "assert": ssh("grep -m1 GGML_ASSERT ~/split73/RA.log") if st == "DEAD" else ""})

for tag in [t for t in ("R", "RL") if t in sys.argv[1:]]:
    if tag == "RL":
        DAILY = DAILY.replace("-sm tensor", "-sm layer")
    ssh(f"rm -rf {STORE}; mkdir -p {STORE}")
    extra = f"--resume --resume-path {STORE}"
    pid, load_s = start(extra, f"{tag}1")
    write({"step": f"{tag}_start1", "load_s": load_s})
    reply = chat(m1, 24, f"{tag}_turn1")
    time.sleep(10)
    t0 = time.time(); ssh(f"kill -TERM {pid}")
    for _ in range(600):
        if alive(pid) == "DEAD": break
        time.sleep(1)
    save_s = round(time.time() - t0, 1)
    write({"step": f"{tag}_shutdown", "save_s": save_s, "store": ssh(f"du -sh {STORE} | cut -f1; ls -la {STORE} | head -8"),
           "log": ssh(f"grep -i -E 'resume|save|GGML_ASSERT' ~/split73/{tag}1.log | tail -6")})
    pid, load_s = start(extra, f"{tag}2")
    write({"step": f"{tag}_start2", "load_s": load_s, "log": ssh(f"grep -i -E 'resume|restor' ~/split73/{tag}2.log | tail -6")})
    chat(m1 + [{"role": "assistant", "content": reply}, q2], 16, f"{tag}_turn2_after_restart")
    time.sleep(3)
    write({"step": f"{tag}_end", "server": alive(pid)})
