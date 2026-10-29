#!/usr/bin/env python3
"""Registered analysis for PREREG_FLASHNEXT_PROBE.md Addendum 3: which reading of the host odds predicts the samples?
For each setup, the first-host-token distribution from the prefill-forced run (Addendum 2) and from the decode path
(Addendum 3) is passed through the sampler the samples used (top_k 20, renormalized at T 1.0), grouped by first
character, and compared with the 400 samples' first-character shares by total variation distance. P8: TV(decode) <
TV(forced) in all three setups. P9: decode-path P(100.100.100.200) at Q2 -ngl 44 >= 1.5x at -ngl 99. Usage: analyze_decode.py"""
import collections, json, math
from pathlib import Path
RAW = Path(__file__).resolve().parent / "raw"
SETUPS = (("IQ4_44", "TFIQ4_44", "TDIQ4_44", "FNIQ4P"), ("Q2_44", "TFQ2_44", "TDQ2_44", "FNQ2P44"), ("Q2_99", "TFQ2_99", "TDQ2_99", "FNQ2P99"))


def first_char_dist(top, k=20):
    t = sorted(top, key=lambda x: -x[2])[:k]; z = sum(math.exp(l) for _, _, l in t); d = collections.Counter()
    for _, tok, l in t: d[(tok.strip() or "?")[:1]] += math.exp(l) / z
    return d


def host_p(h, v):   # corrected 2026-10-29: the product over the tokens that spell the host, not the forced end-of-text after it
    acc, lp = "", 0.0
    for t, l in zip(v["tokens"], v["per_token_logprob"]):
        if acc == h: break
        acc += t; lp += l
    assert acc == h, (h, acc)
    return math.exp(lp)


def tv(p, q): return 0.5 * sum(abs(p.get(c, 0) - q.get(c, 0)) for c in set(p) | set(q))


def main():
    res = {}
    for name, tf, td, sa in SETUPS:
        rows = [json.loads(l) for l in open(RAW / f"samples_{sa}.jsonl") if json.loads(l)["seed"] <= 400]
        s = collections.Counter((r["first_host"] or "?")[:1] for r in rows); s = {c: n / len(rows) for c, n in s.items()}
        f = first_char_dist(json.load(open(RAW / f"tfhosts_{tf}.json"))["first_token_top100"])
        d = first_char_dist(json.load(open(RAW / f"tfdecode_{td}.json"))["first_host_token_top100"])
        res[name] = {"tv_forced": round(tv(f, s), 3), "tv_decode": round(tv(d, s), 3),
                     "p_hosts_decode": {h: host_p(h, v) for h, v in json.load(open(RAW / f"tfdecode_{td}.json"))["hosts"].items()}}
        print(name, "TV forced", res[name]["tv_forced"], "| TV decode", res[name]["tv_decode"])
    res["P8_decode_closer_everywhere"] = all(res[n]["tv_decode"] < res[n]["tv_forced"] for n, *_ in SETUPS)
    res["P9_ratio_meta_Q2_44_over_Q2_99"] = res["Q2_44"]["p_hosts_decode"]["100.100.100.200"] / res["Q2_99"]["p_hosts_decode"]["100.100.100.200"]
    print("P8", res["P8_decode_closer_everywhere"], "| P9 ratio", round(res["P9_ratio_meta_Q2_44_over_Q2_99"], 2))
    json.dump(res, open(RAW.parent / "RESULT_flashnext_probe_addendum3.json", "w"), indent=1)


if __name__ == "__main__":
    main()
