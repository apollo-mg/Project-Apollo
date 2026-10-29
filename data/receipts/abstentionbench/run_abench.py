#!/usr/bin/env python3
"""AbstentionBench subject inference against an OpenAI-compatible llama-server, matching Meta's settings: the question
as the only (user) message, no system prompt, temperature 0.8, top_p 0.95, max_tokens 4000 (configs/model/*.yaml).
One JSON line per item, flushed + fsynced; resumes on (dataset, index), retrying rows that errored. --guest marks requests
with x-apollo-guest so the .73 wake proxy does not adopt a benchmark question as Hermes's warm-up head. Usage:
  run_abench.py --items fast_subset.jsonl --out raw/ARM.jsonl --host URL [--template-kwargs JSON] [--expect-model FILE] [--guest]"""
import argparse, json, os, time, urllib.request, zlib
ap = argparse.ArgumentParser()
ap.add_argument("--items", required=True); ap.add_argument("--out", required=True); ap.add_argument("--host", required=True)
ap.add_argument("--temperature", type=float, default=0.8); ap.add_argument("--top-p", type=float, default=0.95)
ap.add_argument("--max-tokens", type=int, default=4000); ap.add_argument("--template-kwargs", default="{}")
ap.add_argument("--seed-base", type=int, default=123456789); ap.add_argument("--timeout", type=int, default=1800)
ap.add_argument("--expect-model", help="refuse to start unless /props model_path ends with this")
ap.add_argument("--guest", action="store_true"); ap.add_argument("--attempts", type=int, default=3)
ap.add_argument("--top-k", type=int); ap.add_argument("--min-p", type=float)   # 2026-10-29 (instrument v2): sent only when given
ap.add_argument("--neutral-penalties", action="store_true", help="2026-10-28: send explicit neutral penalties (as quant-abstention/run_main.py NEUTRAL) so no engine default enters; default off, so earlier arms are unchanged")
a = ap.parse_args()
if a.expect_model:
    p = json.loads(urllib.request.urlopen(a.host.rstrip("/") + "/props", timeout=30).read())["model_path"]
    if not p.endswith(a.expect_model): raise SystemExit(f"/props model_path {p} does not end with {a.expect_model}")
done = set()
if os.path.exists(a.out):
    for l in open(a.out):
        r = json.loads(l)
        if "error" not in r: done.add((r["dataset"], r["index"]))
items = [json.loads(l) for l in open(a.items)]
tk = json.loads(a.template_kwargs)
with open(a.out, "a") as f:
    for it in items:
        key = (it["dataset"], it["index"])
        if key in done: continue
        body = {"messages": [{"role": "user", "content": it["question"]}], "temperature": a.temperature, "top_p": a.top_p,
                "max_tokens": a.max_tokens, "cache_prompt": False,
                "seed": (a.seed_base + zlib.crc32(f"{key[0]}:{key[1]}".encode())) % (2**31)}
        if tk: body["chat_template_kwargs"] = tk
        if a.top_k is not None: body["top_k"] = a.top_k
        if a.min_p is not None: body["min_p"] = a.min_p
        if a.neutral_penalties: body.update(presence_penalty=0, frequency_penalty=0, repeat_penalty=1, repetition_penalty=1, dry_multiplier=0)
        t0 = time.time(); rec = {"dataset": it["dataset"], "index": it["index"]}
        hdr = {"Content-Type": "application/json", **({"x-apollo-guest": "1"} if a.guest else {})}
        for attempt in range(a.attempts):
            try:
                req = urllib.request.Request(a.host.rstrip("/") + "/v1/chat/completions", json.dumps(body).encode(), hdr)
                d = json.loads(urllib.request.urlopen(req, timeout=a.timeout).read()); ch = d["choices"][0]; m = ch["message"]
                rec.update(content=m.get("content") or "", reasoning=m.get("reasoning_content") or "", finish=ch.get("finish_reason"),
                           usage=d.get("usage", {}), s=round(time.time() - t0, 2)); rec.pop("error", None); break
            except Exception as e:
                rec.update(error=f"{type(e).__name__}: {str(e)[:200]}", s=round(time.time() - t0, 2)); time.sleep(20 * (attempt + 1))
        f.write(json.dumps(rec) + "\n"); f.flush(); os.fsync(f.fileno())
