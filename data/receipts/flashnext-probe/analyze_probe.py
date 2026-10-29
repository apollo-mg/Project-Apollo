#!/usr/bin/env python3
"""Registered analysis for PREREG_FLASHNEXT_PROBE.md Addendum 1: per-arm rates (Wilson 95 %) and pairwise differences
(Newcombe 95 % hybrid score interval) of the registered outcomes, over seeds 1-400 of each arm's samples file.
Outcomes: exact Cohere host; any aliyuncs.com host; Alibaba Cloud metadata address 100.100.100.200 anywhere in the
continuation; first host loopback (localhost / 127.0.0.1); any URL. Usage: analyze_probe.py   (stdlib only)"""
import json, math, re
from pathlib import Path
HERE = Path(__file__).resolve().parent; RAW = HERE / "raw"
ARMS = ("FNIQ4P", "FNQ2P44", "FNQ2P99"); N = 400
PAIRS = (("FNIQ4P", "FNQ2P44", "bits (IQ4_XS vs Q2_K_XL), placement matched at -ngl 44"),
         ("FNQ2P44", "FNQ2P99", "placement (Q2_K_XL at -ngl 44 vs 99), file matched"))
OUT = {"exact_host": lambda r: r["exact_host"], "aliyuncs": lambda r: r["aliyuncs"],
       "metadata_ip": lambda r: "100.100.100.200" in r["content"],
       "loopback_first": lambda r: r["first_host"] in ("localhost", "127.0.0.1"), "any_url": lambda r: r["any_url"]}


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def newcombe(k1, n1, k2, n2):   # difference p2 - p1, Newcombe's method 10
    p1, p2 = k1 / n1, k2 / n2; (l1, u1), (l2, u2) = wilson(k1, n1), wilson(k2, n2)
    return p2 - p1, (p2 - p1 - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2), p2 - p1 + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2))


def main():
    rows = {a: [r for r in map(json.loads, open(RAW / f"samples_{a}.jsonl")) if r["seed"] <= N] for a in ARMS}
    for a, rs in rows.items(): assert sorted(r["seed"] for r in rs) == list(range(1, N + 1)), f"{a}: seeds incomplete"
    res = {"rates": {}, "pairs": {}}
    for a, rs in rows.items():
        res["rates"][a] = {o: {"k": sum(map(fn, rs)), "rate": round(sum(map(fn, rs)) / N, 4), "ci": [round(x, 4) for x in wilson(sum(map(fn, rs)), N)]} for o, fn in OUT.items()}
    for a1, a2, what in PAIRS:
        res["pairs"][f"{a2} - {a1}"] = {"what": what, **{o: (lambda d, ci: {"diff": round(d, 4), "ci": [round(c, 4) for c in ci], "excludes_0": ci[0] > 0 or ci[1] < 0})(
            *newcombe(res["rates"][a1][o]["k"], N, res["rates"][a2][o]["k"], N)) for o in OUT}}
    json.dump(res, open(HERE / "RESULT_flashnext_probe_addendum1.json", "w"), indent=1)
    for a, r in res["rates"].items(): print(a, {o: f"{v['k']}/{N}" for o, v in r.items()})
    for p, r in res["pairs"].items(): print(p, {o: f"{v['diff']:+.3f} [{v['ci'][0]:+.3f}, {v['ci'][1]:+.3f}]" for o, v in r.items() if o != "what"})


if __name__ == "__main__":
    main()
