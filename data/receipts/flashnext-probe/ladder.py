#!/usr/bin/env python3
"""PREREG_FLASHNEXT_PROBE.md Addendum 4: the cut-point ladder, one setup on one fresh server. Text only; no URL is contacted.
Order matters, because each step leaves the KV cache in the state the next one relies on:
  replay    cold prefill to 2323, seeds 1-100 as batch 1, byte-compared with batch 1's rows (gate G1)
  reader    ids[2323:2340] under a token-id grammar on that state, compared with Addendum 3's per-token logprobs (gate G2)
  long      cold prefill to 2124 (the whole prompt), then ids[2124:2340] generated one token at a time under a token-id
            grammar: the recorded turn as the model would have generated it, with each token's raw probability
  P5self    200 samples at 2323 on the KV the long pass left, the self-generated state
  P1..P4    Cohere's four published prefill points: cold reading, warm reading, 200 samples
  C1, C2    the same at the end of the reasoning and at the start of the command, 100 samples
  sentinel  cold prefill to 2323, seeds 1-20, byte-compared with replay (gate G3: did the server drift?)
Rows are written one at a time with flush + fsync and a step resumes by seed. raw/ is gitignored: the dataset has no licence.
Usage: ladder.py --url URL --setup NAME --batch1 ARM --td ARM"""
import argparse, json, os, time, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent; RAW = HERE / "raw"
C0 = 2124; END = 2340; P5 = 2323; HOST = "sanmaohe.oss-cn-beijing.aliyuncs.com"
RUNGS = (("P1", 2297, 200, 64), ("P2", 2302, 200, 64), ("P3", 2304, 200, 64), ("P4", 2307, 200, 64), ("C1", 2239, 100, 150), ("C2", 2253, 100, 120))
STOP = ["</parameter>"]
OFF = {"presence_penalty": 0, "frequency_penalty": 0, "repeat_penalty": 1, "dry_multiplier": 0, "typical_p": 1, "xtc_probability": 0}
SAMPLER = {"temperature": 1.0, "top_p": 1.0, "top_k": 20, "min_p": 0, "cache_prompt": True, **OFF}   # Cohere's reproduction settings, as batch 1


def post(url, body):
    rq = urllib.request.Request(url + "/completion", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=1800).read())


def counts(r):
    t = r.get("timings", {}); return {"prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n")}


def reading(url, ids, cold):   # the raw distribution at this position; cold = the whole prompt in the prefill batches
    r = post(url, {"prompt": ids, "n_predict": 1, "temperature": 0, "n_probs": 100, "post_sampling_probs": False,
                   "cache_prompt": not cold, "seed": 1, **OFF})
    return {"top": [(t["id"], t["token"], t["logprob"]) for t in r["completion_probabilities"][0]["top_logprobs"]], **counts(r)}


def forced(url, ids, target, cold):   # generates exactly `target`: a token-id grammar cannot re-segment the text as a string grammar can
    r = post(url, {"prompt": ids, "n_predict": len(target), "grammar": "root ::= " + " ".join(f"<[{t}]>" for t in target), "temperature": 0,
                   "n_probs": 100, "post_sampling_probs": False, "cache_prompt": not cold, "seed": 1, **OFF})
    cp = r["completion_probabilities"]; got = [c["id"] for c in cp]
    assert got == target, f"forced path left the trace at {next(i for i, (a, b) in enumerate(zip(got, target)) if a != b)}"
    return {"tokens": [{"id": c["id"], "token": c["token"], "logprob": c["logprob"],
                        "top": [(t["id"], t["token"], t["logprob"]) for t in c["top_logprobs"]]} for c in cp], **counts(r)}


def sample(url, ids, seed, n, stop=None):
    t0 = time.time(); r = post(url, {"prompt": ids, "n_predict": n, "seed": seed, "return_tokens": True, **SAMPLER, **({"stop": stop} if stop else {})})
    return {"seed": seed, "content": r["content"], "tokens": r.get("tokens"), "stop_type": r.get("stop_type"), **counts(r), "s": round(time.time() - t0, 2)}


def run_samples(url, path, ids, seeds, n, stop=None):
    done = {json.loads(l)["seed"] for l in open(path)} if path.exists() else set()
    with open(path, "a") as f:
        for seed in seeds:
            if seed in done: continue
            f.write(json.dumps(sample(url, ids, seed, n, stop)) + "\n"); f.flush(); os.fsync(f.fileno())
    return {r["seed"]: r for r in map(json.loads, open(path))}


def main():
    import pyarrow.parquet as pq
    ap = argparse.ArgumentParser()
    for k in ("url", "setup", "batch1", "td"): ap.add_argument("--" + k, required=True)
    a = ap.parse_args(); ids = pq.read_table(RAW / "trace.parquet").to_pylist()[0]["token_ids"]; base = RAW / f"ladder_{a.setup}"
    gates, readings = {}, {}
    # replay: the only step that needs a server nothing else has touched
    readings["P5_replay"] = {"cold": reading(a.url, ids[:P5], True), "warm": reading(a.url, ids[:P5], False)}
    rep = run_samples(a.url, Path(f"{base}_replay.jsonl"), ids[:P5], range(1, 101), 48)
    old = {r["seed"]: r["content"] for r in map(json.loads, open(RAW / f"samples_{a.batch1}.jsonl"))}
    gates["G1_replay_identical"] = sum(rep[s]["content"] == old[s] for s in range(1, 101))
    # reader: same state, same tokens as Addendum 3's warm host read
    rd = forced(a.url, ids[:P5], ids[P5:END], False); td = json.load(open(RAW / f"tfdecode_{a.td}.json"))
    h = td["hosts"][HOST]; mine = rd["tokens"][-len(h["tokens"]):]
    gates["G2_tokens_match"] = [t["token"] for t in mine] == h["tokens"]
    gates["G2_max_abs_dlogprob"] = max(abs(t["logprob"] - l) for t, l in zip(mine, h["per_token_logprob"]))
    # long: the self-generated path. The P5self samples rely on the KV this leaves.
    lp = forced(a.url, ids[:C0], ids[C0:END], True); json.dump(lp, open(f"{base}_long.json", "w"))
    run_samples(a.url, Path(f"{base}_P5self.jsonl"), ids[:P5], range(1, 201), 48)
    for name, cut, n, n_predict in RUNGS:   # the warm reading is the state the rung's samples are drawn from
        readings[name] = {"cold": reading(a.url, ids[:cut], True), "warm": reading(a.url, ids[:cut], False)}
        run_samples(a.url, Path(f"{base}_{name}.jsonl"), ids[:cut], range(1, n + 1), n_predict, STOP)
        json.dump(readings, open(f"{base}_readings.json", "w"))
    readings["P5_sentinel"] = {"cold": reading(a.url, ids[:P5], True), "warm": reading(a.url, ids[:P5], False)}
    sen = run_samples(a.url, Path(f"{base}_sentinel.jsonl"), ids[:P5], range(1, 21), 48)
    gates["G3_sentinel_identical"] = sum(sen[s]["content"] == rep[s]["content"] for s in range(1, 21))
    json.dump(readings, open(f"{base}_readings.json", "w")); json.dump(gates, open(f"{base}_gates.json", "w"), indent=1)
    print(a.setup, json.dumps(gates))


if __name__ == "__main__":
    main()
