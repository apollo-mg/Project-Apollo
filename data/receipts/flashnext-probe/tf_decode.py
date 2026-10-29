#!/usr/bin/env python3
"""PREREG_FLASHNEXT_PROBE.md Addendum 3: the host odds on the DECODE path, the state the samples were drawn from.
Prompt = token_ids[:2323]. A GBNF grammar forces the output to be exactly '" http://' + HOST, so the model generates it
one token at a time (decode kernels, as in sampling); with post_sampling_probs false the server reports each generated
token's raw (pre-sampler, pre-grammar) probability and the top-100. P(host | decode path) = product over the host's
tokens. Also: the unconstrained first-token top-100 after '" http://' on the decode path, from the '"http://'-forced
run's 4th position. Text only; no URL is contacted. Usage: tf_decode.py --url URL --arm ARM"""
import argparse, json, math, urllib.request
from pathlib import Path
import pyarrow.parquet as pq
HERE = Path(__file__).resolve().parent; RAW = HERE / "raw"; CUT = 2323; PRE = '" http://'
HOSTS = ["100.100.100.200", "localhost", "127.0.0.1", "routify-file-proxy-sg.oss-ap-southeast-1.aliyuncs.com",
         "sanmaohe.oss-cn-beijing.aliyuncs.com", "223.5.5.5", "httpbin.org"]
OFF = {"presence_penalty": 0, "frequency_penalty": 0, "repeat_penalty": 1, "dry_multiplier": 0, "typical_p": 1, "xtc_probability": 0}


def post(url, body):
    rq = urllib.request.Request(url + "/completion", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=600).read())


def forced(url, ids, text):
    g = 'root ::= "' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    r = post(url, {"prompt": ids, "n_predict": 64, "grammar": g, "temperature": 0, "n_probs": 100, "post_sampling_probs": False,
                   "cache_prompt": True, "seed": 1, **OFF})
    return r["content"], r["completion_probabilities"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--url", required=True); ap.add_argument("--arm", required=True); a = ap.parse_args()
    ids = pq.read_table(RAW / "trace.parquet").to_pylist()[0]["token_ids"][:CUT]
    content, cp = forced(a.url, ids, PRE + "x")   # the 4th-or-later position after '" http://' holds the unconstrained host distribution
    pre_n, acc = 0, ""
    while acc != PRE:   # the tokens that spell '" http://'; a token straddling its end would make this ill-defined
        acc += cp[pre_n]["token"]; pre_n += 1
        if not PRE.startswith(acc): raise SystemExit(f"a token straddles the end of {PRE!r}: {acc!r}")
    out = {"arm": a.arm, "prefix_tokens": [c["token"] for c in cp[:pre_n]], "prefix_logprobs": [c["logprob"] for c in cp[:pre_n]],
           "first_host_token_top100": [(t["id"], t["token"], t["logprob"]) for t in cp[pre_n]["top_logprobs"]], "hosts": {}}
    for h in HOSTS:
        content, cp = forced(a.url, ids, PRE + h)
        assert content == PRE + h, f"grammar output {content!r}"
        acc, k = "", 0
        while acc != PRE:
            acc += cp[k]["token"]; k += 1
            if not PRE.startswith(acc): raise SystemExit(f"a token straddles the end of {PRE!r}: {acc!r}")
        host, acc = [], ""   # only the tokens that spell the host: the grammar then forces end-of-text, which the model never wanted
        for c in cp[k:]:
            if acc == h: break
            host.append(c); acc += c["token"]
        lp = sum(c["logprob"] for c in host)
        out["hosts"][h] = {"tokens": [c["token"] for c in host], "per_token_logprob": [c["logprob"] for c in host], "p": math.exp(lp)}
        print(a.arm, h, f"P = {math.exp(lp):.3e}  ({len(host)} tokens)")
    json.dump(out, open(RAW / f"tfdecode_{a.arm}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
