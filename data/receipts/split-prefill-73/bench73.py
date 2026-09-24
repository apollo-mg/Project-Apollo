#!/usr/bin/env python3
"""PREREG_SPLIT_PREFILL_73.md. Runs on the desktop against a llama-server already started on .73.
usage: bench73.py depth LABEL OUT.jsonl       (legs T and L: depth sweep + 2k sticky-floor probe)
       bench73.py reuse LABEL OUT.jsonl       (leg L4: turn1, turn2, side, turn3, concurrent side+turn4)
Every record is appended with flush+fsync as soon as it exists."""
import json, os, sys, threading, time, urllib.request
from pathlib import Path

URL = "http://10.0.0.73:8080"
HERE = Path(__file__).parent
CORPUS = HERE.parent / "quant-hesitation" / "corpus_reasoning.txt"
IDS = HERE / "raw" / "corpus_ids.json"
MODE, LABEL, OUT = sys.argv[1:4]

def req(path, body=None, timeout=3600):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(URL + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read())

def write(rec):
    rec = {"label": LABEL, "t": time.time(), **rec}
    with open(OUT, "a") as f:
        f.write(json.dumps(rec) + "\n"); f.flush(); os.fsync(f.fileno())
    print(json.dumps({k: v for k, v in rec.items() if k not in ("poll", "content")})[:400], flush=True)

def slots():
    try:
        return [{k: s.get(k) for k in ("id", "is_processing", "kv_bpv", "n_ctx")} for s in req("/slots", timeout=30)]
    except Exception as e:
        return [{"error": repr(e)}]

class Poller(threading.Thread):
    def __init__(self): super().__init__(daemon=True); self.stop = False; self.rows = []
    def run(self):
        t0 = time.time()
        while not self.stop:
            self.rows.append([round(time.time() - t0, 1), slots()]); time.sleep(5)

def completion(tokens, name, n_predict=256):
    before = slots(); p = Poller(); p.start(); t0 = time.time()
    try:
        r = req("/completion", {"prompt": tokens, "n_predict": n_predict, "temperature": 0, "top_k": 1,
                                "ignore_eos": True, "cache_prompt": False})
        err = None
    except Exception as e:
        r, err = {}, repr(e)
    wall = time.time() - t0; p.stop = True; p.join(timeout=10)
    write({"kind": "completion", "name": name, "n_prompt": len(tokens), "wall_s": round(wall, 2), "error": err,
           "timings": r.get("timings"), "tokens_predicted": r.get("tokens_predicted"),
           "slots_before": before, "slots_after": slots(), "poll": p.rows})

def ready():
    for _ in range(360):
        try:
            if req("/health", timeout=5).get("status") == "ok": break
        except Exception: pass
        time.sleep(5)
    r = req("/completion", {"prompt": "The capital of France is", "n_predict": 16, "temperature": 0}, timeout=600)
    assert r.get("tokens_predicted", 0) > 0, r
    write({"kind": "warmup", "tokens_predicted": r["tokens_predicted"], "slots": slots()})

def corpus_ids():
    if IDS.exists(): return json.load(open(IDS))
    ids = req("/tokenize", {"content": CORPUS.read_text(), "add_special": False}, timeout=600)["tokens"]
    IDS.parent.mkdir(exist_ok=True); json.dump(ids, open(IDS, "w")); return ids

def chat(messages, name, max_tokens=200):
    t0 = time.time()
    try:
        r = req("/v1/chat/completions", {"messages": messages, "max_tokens": max_tokens, "temperature": 0,
                                         "chat_template_kwargs": {"enable_thinking": False}}, timeout=1800)
        err = None
    except Exception as e:
        r, err = {}, repr(e)
    content = (r.get("choices") or [{}])[0].get("message", {}).get("content")
    write({"kind": "chat", "name": name, "wall_s": round(time.time() - t0, 2), "error": err,
           "timings": r.get("timings"), "usage": r.get("usage"), "content_len": len(content or ""),
           "slots": slots()})
    return content or ""

ready()
if MODE == "depth":
    ids = corpus_ids(); write({"kind": "corpus", "n_ids": len(ids)})
    assert len(ids) >= 215040, len(ids)
    for name, a, b in (("d128k", 0, 131072), ("d64k", 131072, 196608), ("d16k", 196608, 212992),
                       ("probe2k", 212992, 215040)):
        completion(ids[a:b], name)
elif MODE == "reuse":
    text = CORPUS.read_text()[:10000]
    sys_msg = {"role": "system", "content": "You are a careful assistant. Reference notes follow.\n\n" + text}
    m = [sys_msg, {"role": "user", "content": "In two sentences, what is the first question in these notes about?"}]
    a1 = chat(m, "turn1"); m += [{"role": "assistant", "content": a1},
                                 {"role": "user", "content": "And what answer did the notes reach?"}]
    a2 = chat(m, "turn2")
    chat([{"role": "user", "content": "Write a 4-word title for: a chat about reference notes."}], "side", 20)
    m += [{"role": "assistant", "content": a2}, {"role": "user", "content": "Name one assumption it relied on."}]
    a3 = chat(m, "turn3")
    m += [{"role": "assistant", "content": a3}, {"role": "user", "content": "Is that assumption justified?"}]
    th = threading.Thread(target=chat, args=(m, "turn4_concurrent")); th.start(); time.sleep(1.0)
    chat([{"role": "user", "content": "Write a 4-word title for: assumptions in notes."}], "side_concurrent", 20)
    th.join()
    write({"kind": "end", "health": req("/health", timeout=10)})
