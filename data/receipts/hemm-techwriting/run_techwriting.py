#!/usr/bin/env python3
"""Generate every task on one or two live arms (PREREG_HEMM_TECHWRITING.md).
usage: run_techwriting.py ARM=URL [ARM=URL ...]     e.g.  S5=http://10.0.0.194:8084 H5=http://10.0.0.194:8085
Resumable: one JSONL per arm under raw/, a task already present is skipped. Arms run concurrently."""
import json, sys, threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
TASKS = json.load(open(HERE / "tasks_private.json"))["tasks"]   # local-only full set (see tasks.json note)
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 0.0}


def props(url):
    return json.load(urllib.request.urlopen(url + "/props", timeout=30))


def gen(url, prompt, seed):
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": 8000, "seed": seed,
            "chat_template_kwargs": {"reasoning_effort": "medium"}, **SAMPLING}
    t0 = time.time()
    r = json.load(urllib.request.urlopen(urllib.request.Request(
        url + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"}),
        timeout=3600))
    c = r["choices"][0]
    return {"content": c["message"].get("content") or "", "reasoning": c["message"].get("reasoning_content") or "",
            "finish_reason": c.get("finish_reason"), "usage": r.get("usage"), "secs": round(time.time() - t0, 1)}


def run_arm(arm, url):
    out = HERE / "raw" / f"{arm}.jsonl"; out.parent.mkdir(exist_ok=True)
    outl = HERE / "raw" / f"{arm}_ledger.jsonl"   # gitignored: diary text summarizes private chat
    done = set()
    for f in (out, outl):
        if f.exists(): done |= {json.loads(l)["id"] for l in open(f)}
    for i, t in enumerate(TASKS):
        if t["id"] in done:
            continue
        try:
            res = gen(url, t["user_prompt"], 1000 + i)
        except Exception as e:
            res = {"error": f"{type(e).__name__}: {e}"}
        row = {"id": t["id"], "kind": t["kind"], "arm": arm, **res}
        with open(outl if t["kind"] == "ledger" else out, "a") as f:
            f.write(json.dumps(row) + "\n"); f.flush()
        print(f"{arm} {t['id']:16s} {res.get('finish_reason')} {len(res.get('content','').split())} words "
              f"{res.get('secs')} s", flush=True)


if __name__ == "__main__":
    arms = dict(a.split("=", 1) for a in sys.argv[1:])
    meta = {}
    for arm, url in arms.items():
        p = props(url)
        meta[arm] = {"model_path": p.get("model_path"), "chat_template_sha": __import__("hashlib").sha256(
            (p.get("chat_template") or "").encode()).hexdigest()[:16],
            "server_defaults": {k: p["default_generation_settings"]["params"].get(k)
                                for k in ("temperature", "top_p", "top_k", "min_p")}}
        print(arm, meta[arm], flush=True)
    (HERE / "raw").mkdir(exist_ok=True)
    with open(HERE / "raw" / "props.jsonl", "a") as f:
        f.write(json.dumps({"ts": time.time(), **meta}) + "\n")
    th = [threading.Thread(target=run_arm, args=(a, u)) for a, u in arms.items()]
    [t.start() for t in th]; [t.join() for t in th]
    print("DONE", flush=True)
