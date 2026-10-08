#!/usr/bin/env python3
"""PREREG_KMIC_VS_DAILY_73.md. Runs on the desktop against a llama-server already started on .73.
usage: kbench.py micro  LABEL OUT.jsonl          (M1: 2k prompt, 256 tokens at temperature 0, 3 reps)
       kbench.py served LABEL OUT.jsonl DEPTHS   (M2: DEPTHS like 2k,32k,128k; model-card sampling, seeds 1/2)
Every record is appended with flush+fsync as soon as it exists."""
import base64, json, os, sys, time, urllib.request
from pathlib import Path

URL = "http://10.0.0.73:8080"
HERE = Path(__file__).parent
REC = HERE.parent / "split-prefill-73"
IDS = REC / "raw" / "corpus_ids.json"
CORPUS = REC.parent / "quant-hesitation" / "corpus_reasoning.txt"
IMAGE = REC / "media_probe.png"
SLICES = {"2k": (212992, 215040), "32k": (131072, 163840), "128k": (0, 131072)}
SEEDS = {"2k": (1, 2), "32k": (1, 2), "128k": (1,)}
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
    print(json.dumps({k: v for k, v in rec.items() if k != "content"})[:500], flush=True)


def collapse_stats(text):
    """V2: longest run of one character, and the number of distinct characters."""
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
           "collapse": collapse_stats(content), "content": content})


def ready():
    for _ in range(360):
        try:
            if req("/health", timeout=5).get("status") == "ok":
                break
        except Exception:
            pass
        time.sleep(5)
    r = req("/completion", {"prompt": "The capital of France is", "n_predict": 16, "temperature": 0}, timeout=600)
    assert r.get("tokens_predicted", 0) > 0, r
    write({"kind": "warmup", "tokens_predicted": r["tokens_predicted"]})


def tokenizer_check(ids):
    """V1: the server's tokenization of the first 4,000 corpus characters matches the stored ids' prefix."""
    got = req("/tokenize", {"content": CORPUS.read_text()[:4000], "add_special": False}, timeout=120)["tokens"]
    n = len(got) - 1   # the last token can merge with what follows the cut
    write({"kind": "v1_tokenizer", "n": n, "match": got[:n] == ids[:n]})


def vision_check():
    """V3: one image request returns non-empty content."""
    uri = "data:image/png;base64," + base64.b64encode(IMAGE.read_bytes()).decode()
    t0 = time.time()
    try:
        r = req("/v1/chat/completions", {
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Describe this image in one sentence."},
                {"type": "image_url", "image_url": {"url": uri}}]}],
            "max_tokens": 120, "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}, timeout=600)
        err = None
    except Exception as e:
        r, err = {}, repr(e)
    content = ((r.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    write({"kind": "v3_vision", "wall_s": round(time.time() - t0, 2), "error": err, "content_len": len(content),
           "content": content, "timings": r.get("timings")})


ready()
ids = json.load(open(IDS))
tokenizer_check(ids)
if MODE == "micro":
    a, b = SLICES["2k"]
    for rep in range(3):
        completion(ids[a:b], f"micro_r{rep}", {"n_predict": 256, "temperature": 0, "top_k": 1})
elif MODE == "served":
    for depth in sys.argv[4].split(","):
        a, b = SLICES[depth]
        for seed in SEEDS[depth]:
            completion(ids[a:b], f"d{depth}_s{seed}", {"n_predict": 512, "temperature": 1.0, "top_k": 20,
                                                     "top_p": 0.95, "min_p": 0.0, "seed": seed})
    if LABEL in ("D1", "K1"):
        vision_check()
write({"kind": "end", "health": req("/health", timeout=10)})
