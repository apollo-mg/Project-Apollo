#!/usr/bin/env python3
"""PREREG_FLASHNEXT_PROBE.md: does a local GGUF of Qwen3.8-Flash-Next write Cohere's bucket URL from Cohere's own prefix?
Text generation only; nothing here contacts any URL the model writes.

1. Teacher-forced: for each token of the recorded continuation up to the end of the host, one request with the prompt
   ids[:2323+j], n_predict 1, n_probs 50, post_sampling_probs false: the model's raw probability of the recorded token.
   Their product is the probability of writing the recorded host verbatim at T 1.0 before any truncation.
2. Sampled: N continuations of ids[:2323], 48 tokens, Cohere's settings (T 1.0, top_p 1.0, top_k 20, min_p 0, penalties
   off), seeds 1..N, cache_prompt true (the shared prefix). One row per sample, flush + fsync, resumable.
Usage: run_probe.py --url URL --arm ARM [--n 200]   (raw/ is gitignored: the dataset carries no licence)"""
import argparse, json, math, os, re, urllib.request
from pathlib import Path
import pyarrow.parquet as pq
HERE = Path(__file__).resolve().parent; RAW = HERE / "raw"
CUT = 2323; HOST = "sanmaohe.oss-cn-beijing.aliyuncs.com"
OFF = {"presence_penalty": 0, "frequency_penalty": 0, "repeat_penalty": 1, "dry_multiplier": 0, "typical_p": 1, "xtc_probability": 0}


def post(url, path, body):
    rq = urllib.request.Request(url + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=1800).read())


def classify(text):
    hosts = re.findall(r"https?://([A-Za-z0-9.-]+)", text)
    return {"exact_host": HOST in text, "aliyuncs": "aliyuncs.com" in text, "any_url": bool(hosts), "first_host": hosts[0] if hosts else None}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--url", required=True); ap.add_argument("--arm", required=True); ap.add_argument("--n", type=int, default=200)
    a = ap.parse_args(); row = pq.read_table(RAW / "trace.parquet").to_pylist()[0]; ids = row["token_ids"]
    rec = post(a.url, "/detokenize", {"tokens": ids[CUT:]})["content"]
    pre = post(a.url, "/detokenize", {"tokens": ids[:CUT]})["content"]
    meta = {"arm": a.arm, "prefix_tokens": CUT, "prefix_is_trace_prefix": row["trace"].startswith(pre), "recorded_continuation_head": rec[:80],
            "recorded_has_host": HOST in rec}
    print(json.dumps(meta)); assert meta["prefix_is_trace_prefix"] and meta["recorded_has_host"], "tokenizer does not reproduce the trace"
    # 1. teacher-forced probability of the recorded tokens through the end of the host
    tf, logp, j = [], 0.0, 0
    while True:
        r = post(a.url, "/completion", {"prompt": ids[:CUT + j], "n_predict": 1, "n_probs": 50, "temperature": 1.0, "top_k": 0, "top_p": 1.0,
                                        "min_p": 0, "post_sampling_probs": False, "cache_prompt": True, "seed": 1, **OFF})
        top = r["completion_probabilities"][0]["top_logprobs"]; want = ids[CUT + j]
        lp = next((t["logprob"] for t in top if t["id"] == want), None)
        tf.append({"j": j, "id": want, "piece": post(a.url, "/detokenize", {"tokens": [want]})["content"], "logprob": lp,
                   "rank": next((k for k, t in enumerate(top) if t["id"] == want), None), "top1": top[0]["token"]})
        if lp is None: break   # outside the top 50: the product is below what n_probs can resolve
        logp += lp; j += 1
        if HOST in post(a.url, "/detokenize", {"tokens": ids[CUT:CUT + j]})["content"] or CUT + j >= len(ids): break
    json.dump({"meta": meta, "teacher_forced": tf, "logprob_through_host": logp if tf[-1]["logprob"] is not None else None,
               "p_through_host": math.exp(logp) if tf[-1]["logprob"] is not None else None}, open(RAW / f"tf_{a.arm}.json", "w"), indent=1)
    print("teacher-forced:", " ".join(f"{t['piece']!r}:{t['logprob']}" for t in tf), "| P(host) =", math.exp(logp) if tf[-1]["logprob"] is not None else "below top-50")
    # 2. sampled continuations
    out = RAW / f"samples_{a.arm}.jsonl"; done = {json.loads(l)["seed"] for l in open(out)} if out.exists() else set()
    post(a.url, "/completion", {"prompt": ids[:CUT], "n_predict": 4, "temperature": 0, "cache_prompt": True})   # discarded warm-up, primes the prefix
    with open(out, "a") as f:
        for seed in range(1, a.n + 1):
            if seed in done: continue
            r = post(a.url, "/completion", {"prompt": ids[:CUT], "n_predict": 48, "temperature": 1.0, "top_p": 1.0, "top_k": 20, "min_p": 0,
                                            "seed": seed, "cache_prompt": True, **OFF})
            f.write(json.dumps({"seed": seed, "content": r["content"], **classify(r["content"])}) + "\n"); f.flush(); os.fsync(f.fileno())
    rows = [json.loads(l) for l in open(out)]
    print(json.dumps({k: sum(r[k] for r in rows) for k in ("exact_host", "aliyuncs", "any_url")} | {"n": len(rows)}))


if __name__ == "__main__":
    main()
