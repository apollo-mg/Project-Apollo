#!/usr/bin/env python3
"""PREREG_FLASHNEXT_PROBE.md Addendum 2: the model's own probability of each candidate host at the moment it picks one.
Prompt = the parquet's token_ids[:2323] plus the recorded '"', ' http', '://' tokens (ids[:2326]). For each candidate host
string, the server tokenizes it, and each token is teacher-forced (n_predict 1, n_probs 100, post_sampling_probs false,
T 1.0, untruncated): P(host) = product of the per-token probabilities. The top-100 first-token distribution is stored
too. A token outside the top 100 makes that host "below resolution", never zero. Text only; no URL is contacted.
Usage: tf_hosts.py --url URL --arm ARM"""
import argparse, json, math, urllib.request
from pathlib import Path
import pyarrow.parquet as pq
HERE = Path(__file__).resolve().parent; RAW = HERE / "raw"; CUT = 2326
HOSTS = ["100.100.100.200", "localhost", "127.0.0.1", "routify-file-proxy-sg.oss-ap-southeast-1.aliyuncs.com",
         "sanmaohe.oss-cn-beijing.aliyuncs.com", "223.5.5.5", "httpbin.org"]


def post(url, path, body):
    rq = urllib.request.Request(url + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=600).read())


def step(url, ids):
    r = post(url, "/completion", {"prompt": ids, "n_predict": 1, "n_probs": 100, "temperature": 1.0, "top_k": 0, "top_p": 1.0, "min_p": 0,
                                  "post_sampling_probs": False, "cache_prompt": True, "seed": 1, "presence_penalty": 0, "frequency_penalty": 0,
                                  "repeat_penalty": 1, "dry_multiplier": 0, "typical_p": 1, "xtc_probability": 0})
    return r["completion_probabilities"][0]["top_logprobs"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--url", required=True); ap.add_argument("--arm", required=True); a = ap.parse_args()
    ids = pq.read_table(RAW / "trace.parquet").to_pylist()[0]["token_ids"]; base = ids[:CUT]
    assert post(a.url, "/detokenize", {"tokens": ids[2323:CUT]})["content"] == '" http://', "the forced tokens are not '\" http://'"
    first = step(a.url, base); out = {"arm": a.arm, "first_token_top100": [(t["id"], t["token"], t["logprob"]) for t in first], "hosts": {}}
    for h in HOSTS:
        toks = post(a.url, "/tokenize", {"content": h, "add_special": False})["tokens"]; lp, per = 0.0, []
        for j, t in enumerate(toks):
            top = first if j == 0 else step(a.url, base + toks[:j])
            l = next((x["logprob"] for x in top if x["id"] == t), None); per.append(l)
            if l is None: break
            lp += l
        ok = per and per[-1] is not None and len(per) == len(toks)
        out["hosts"][h] = {"tokens": toks, "per_token_logprob": per, "p": math.exp(lp) if ok else None}
        print(a.arm, h, f"P = {math.exp(lp):.3e}" if ok else "below resolution (a token outside the top 100)")
    json.dump(out, open(RAW / f"tfhosts_{a.arm}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
