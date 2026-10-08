#!/usr/bin/env python3
"""PREREG_UB_DAILY_73.md. Runs on the desktop against a llama-server already started on .73.
usage: ubbench.py LABEL OUT.jsonl
The served schedule of kmic-p100-73's D1 leg (2k seeds 1-2, 32k seeds 1-2, 128k seed 1; 512 tokens, model-card
sampling), plus a per-GPU nvidia-smi memory snapshot after load (before any request), after the warmup and after
every completion. Every record is appended with flush+fsync as soon as it exists."""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

URL = "http://10.0.0.73:8080"
HERE = Path(__file__).parent
REC = HERE.parent / "split-prefill-73"
IDS = REC / "raw" / "corpus_ids.json"
SLICES = {"2k": (212992, 215040), "32k": (131072, 163840), "128k": (0, 131072)}
SCHEDULE = [("2k", 1), ("2k", 2), ("32k", 1), ("32k", 2), ("128k", 1)]
LABEL, OUT = sys.argv[1:3]


def req(path, body=None, timeout=3600):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(URL + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read())


def write(rec):
    rec = {"label": LABEL, "t": time.time(), **rec}
    with open(OUT, "a") as f:
        f.write(json.dumps(rec) + "\n"); f.flush(); os.fsync(f.fileno())
    print(json.dumps({k: v for k, v in rec.items() if k != "content"})[:500], flush=True)


def mem():
    """[[index, used MiB, total MiB], ...] from nvidia-smi on .73, or the error text."""
    try:
        out = subprocess.run(["ssh", "10.0.0.73", "nvidia-smi --query-gpu=index,memory.used,memory.total "
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30).stdout
        return [[int(x) for x in line.split(",")] for line in out.strip().splitlines()]
    except Exception as e:
        return repr(e)


def collapse_stats(text):
    run = best = 0
    prev = None
    for c in text:
        run = run + 1 if c == prev else 1
        best = max(best, run); prev = c
    return {"maxrun": best, "uniq": len(set(text)), "len": len(text)}


def completion(tokens, name, body):
    t0 = time.time()
    try:
        r = req("/completion", {"prompt": tokens, "ignore_eos": True, "cache_prompt": False, **body})
        err = None
    except Exception as e:
        r, err = {}, repr(e)
    content = r.get("content") or ""
    write({"kind": "completion", "name": name, "n_prompt": len(tokens), "wall_s": round(time.time() - t0, 2),
           "error": err, "timings": r.get("timings"), "tokens_predicted": r.get("tokens_predicted"),
           "collapse": collapse_stats(content), "mem": mem(), "content": content})


ok = False
for _ in range(360):
    try:
        if req("/health", timeout=5).get("status") == "ok":
            ok = True
            break
    except Exception:
        pass
    time.sleep(5)
write({"kind": "loaded", "health_ok": ok, "mem": mem()})
if not ok:
    sys.exit(3)
r = req("/completion", {"prompt": "The capital of France is", "n_predict": 16, "temperature": 0}, timeout=600)
assert r.get("tokens_predicted", 0) > 0, r
write({"kind": "warmup", "tokens_predicted": r["tokens_predicted"], "mem": mem()})
ids = json.load(open(IDS))
for depth, seed in SCHEDULE:
    a, b = SLICES[depth]
    completion(ids[a:b], f"d{depth}_s{seed}", {"n_predict": 512, "temperature": 1.0, "top_k": 20,
                                               "top_p": 0.95, "min_p": 0.0, "seed": seed})
write({"kind": "end", "health": req("/health", timeout=10), "mem": mem()})
