#!/usr/bin/env python3
"""Static KV on .73 as a way around the VBR artifact-store abort (INCIDENT_73_NP1_IDLE_REUSE_ABORT).
Daily build 08826ad6e, daily flags except -ctk/-ctv/-np, no --vbr-*, and -c 131072: at 262144 a static cache leaves no room for the mmproj (clip load OOM, observed 10:45). Mark's pre-VBR go-to pairs:
  T8T4 = -ctk turbo8 -ctv turbo4      Q8T4 = -ctk q8_0 -ctv turbo4
usage: static_kv_test.py CONFIG MODE   MODE np1: turn 1, 30 s idle, turn 2 extending it (the V5 crash repro)
                                       MODE np4: turn1, turn2, side, turn3, then side concurrent with turn4
Prior art: INDEX L161 (q8_0+turbo4 aborted on buun 87c351d28), L162/L165 (mixed stock types abort under -sm tensor),
L154 (stock-quantized K+V collapse on sm_60). Appends raw/static_kv_test.jsonl."""
import json, os, subprocess, sys, threading, time, urllib.request
from pathlib import Path
from warm_crash_repro_lib import system, tools, KW
NODE = "http://10.0.0.73:8080"
OUT = Path(__file__).parent / "raw" / "static_kv_test.jsonl"
BIN = os.environ.get("BIN_OVERRIDE", "~/buun-llama-cpp/build_sm60_0920/bin/llama-server")   # default: daily build 08826ad6e
KV = {"T8T4": "-ctk turbo8 -ctv turbo4", "Q8T4": "-ctk q8_0 -ctv turbo4",
      "VBR": "-ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto"}   # VBR: to retest the fix in buun 0b2789f23
CTX = {"VBR": 262144}
CFG, MODE = sys.argv[1], sys.argv[2]
NP = 4 if MODE == "np4" else 1
FLAGS = ("-m '/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf' --mmproj '/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf' "
         f"-ngl 99 -c {CTX.get(CFG, 131072)} {KV[CFG]} -np {NP} -fit off -sm tensor -fa on --spec-type draft-mtp --draft-max 3 --jinja "
         "--kv-unified --chat-template-kwargs '{\"reasoning_effort\":\"medium\"}' --temp 1.0 --top-p 0.95 --top-k 20 "
         "--min-p 0.0 --presence-penalty 0.0 --host 0.0.0.0 --port 8080")
TAG = f"{CFG}_{MODE}" + os.environ.get("TAG_SUFFIX", "")

def call(method, path, body=None, timeout=900):
    r = urllib.request.Request(NODE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read() or b"{}")

def ssh(cmd, timeout=700):
    return subprocess.run(["ssh", "10.0.0.73", cmd], capture_output=True, text=True, timeout=timeout).stdout.strip()

def write(rec):
    with open(OUT, "a") as f:
        f.write(json.dumps({"t": time.time(), "tag": TAG, **rec}) + "\n"); f.flush(); os.fsync(f.fileno())
    print(json.dumps(rec)[:320], flush=True)

def chat(m, max_tokens, name):
    t0 = time.time(); err = None; t = {}; reply = ""
    try:
        r = call("POST", "/v1/chat/completions", {"messages": m, "tools": tools, "max_tokens": max_tokens,
                                                  "temperature": 0, **KW})
        t = r.get("timings", {}); reply = r["choices"][0]["message"].get("content") or ""
    except Exception as e:
        err = repr(e)
    write({"step": name, "wall_s": round(time.time() - t0, 2), "cache_n": t.get("cache_n"), "prompt_n": t.get("prompt_n"),
           "prompt_tps": t.get("prompt_per_second"), "decode_tps": t.get("predicted_per_second"), "error": err,
           "reply": reply[:160]})
    return reply

ssh("pkill -x llama-server; for i in $(seq 120); do pgrep -x llama-server >/dev/null || break; sleep 5; done; sleep 3")
ssh(f"mkdir -p ~/split73; setsid nohup {BIN} {FLAGS} > ~/split73/{TAG}.log 2>&1 < /dev/null & echo $! > ~/split73/{TAG}.pid")
up = False
for _ in range(150):
    try:
        up = call("GET", "/health", timeout=5).get("status") == "ok"
        if up: break
    except Exception: pass
    if ssh(f"kill -0 $(cat ~/split73/{TAG}.pid) 2>/dev/null && echo a || echo d") == "d": break
    time.sleep(3)
pid = ssh(f"cat ~/split73/{TAG}.pid")
if not up:
    write({"step": "startup", "ok": False, "log": ssh(f"grep -v -E '^\\S+ D ' ~/split73/{TAG}.log | grep -E ' E |GGML_ASSERT|abort|error' | head -4")})
    sys.exit(0)
write({"step": "startup", "ok": True, "kv_lines": ssh(f"grep -E 'KV buffer size|K \\(|V \\(' ~/split73/{TAG}.log | head -4")})
m1 = [{"role": "system", "content": system}, {"role": "user", "content": "Name one claim it makes, briefly."}]
if MODE == "np1":
    a1 = chat(m1, 48, "turn1")
    time.sleep(30)
    chat(m1 + [{"role": "assistant", "content": a1}, {"role": "user", "content": "Why might that be wrong? One line."}], 48, "turn2_after_30s")
else:
    a1 = chat(m1, 48, "turn1")
    m = m1 + [{"role": "assistant", "content": a1}, {"role": "user", "content": "Why might that be wrong? One line."}]
    a2 = chat(m, 48, "turn2")
    chat([{"role": "user", "content": "Write a 4-word title for: a chat about reference notes."}], 16, "side")
    m += [{"role": "assistant", "content": a2}, {"role": "user", "content": "Name one assumption it relied on."}]
    a3 = chat(m, 48, "turn3")
    m += [{"role": "assistant", "content": a3}, {"role": "user", "content": "Is that assumption justified?"}]
    th = threading.Thread(target=chat, args=(m, 48, "turn4_concurrent")); th.start(); time.sleep(1.0)
    chat([{"role": "user", "content": "Write a 4-word title for: assumptions in notes."}], 16, "side_concurrent")
    th.join()
time.sleep(3)
st = ssh(f"kill -0 {pid} 2>/dev/null && echo alive || echo DEAD")
write({"step": "end", "server": st, "assert": ssh(f"grep -m1 -E 'GGML_ASSERT|abort' ~/split73/{TAG}.log") if st == "DEAD" else ""})
