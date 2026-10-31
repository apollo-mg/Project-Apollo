#!/usr/bin/env python3
"""PREREG_FLASHNEXT_PROBE.md Addendum 4, Deviation 2: samples from the self-generated state, which ladder.py's P5self did
not reach. Flash-Next's memory cannot be rolled back, so a request at 2323 restores a checkpoint, and the only checkpoint
near there was left by a prefill. Here one request carries the whole path: a token-id grammar forces ids[2124:2323], one
decode at a time, then a free tail is sampled at batch 1's settings for 48 tokens. Nothing between C0 and the first free
token is prefilled or restored. Text only; no URL is contacted. Usage: ladder_self.py --url URL --setup NAME"""
import argparse, json, os, time, urllib.request
from ladder import C0, P5, RAW, SAMPLER, post, reading
GEN = 48; N = 100


def detokenize(url, toks):
    rq = urllib.request.Request(url + "/detokenize", json.dumps({"tokens": toks}).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=60).read())["content"]


def main():
    import pyarrow.parquet as pq
    ap = argparse.ArgumentParser(); ap.add_argument("--url", required=True); ap.add_argument("--setup", required=True); a = ap.parse_args()
    ids = pq.read_table(RAW / "trace.parquet").to_pylist()[0]["token_ids"]; fix = ids[C0:P5]; path = RAW / f"ladder_{a.setup}_selfgen.jsonl"
    grammar = "root ::= " + " ".join(f"<[{t}]>" for t in fix) + " tail\ntail ::= .*\n"
    reading(a.url, ids[:C0], True)   # discarded: the cold prefill leaves the checkpoint, so every row below starts from the same state
    done = {json.loads(l)["seed"] for l in open(path)} if path.exists() else set()
    with open(path, "a") as f:
        for seed in range(1, N + 1):
            if seed in done: continue
            t0 = time.time()
            r = post(a.url, {"prompt": ids[:C0], "n_predict": len(fix) + GEN, "grammar": grammar, "seed": seed, "return_tokens": True, **SAMPLER})
            toks = r["tokens"]; assert toks[:len(fix)] == fix, f"seed {seed} left the trace"
            f.write(json.dumps({"seed": seed, "content": detokenize(a.url, toks[len(fix):]), "tokens": toks[len(fix):], "stop_type": r.get("stop_type"),
                                "prompt_n": r["timings"]["prompt_n"], "cache_n": r["timings"]["cache_n"], "predicted_n": r["timings"]["predicted_n"],
                                "s": round(time.time() - t0, 2)}) + "\n"); f.flush(); os.fsync(f.fileno())
    print(a.setup, "selfgen rows", sum(1 for _ in open(path)))


if __name__ == "__main__":
    main()
