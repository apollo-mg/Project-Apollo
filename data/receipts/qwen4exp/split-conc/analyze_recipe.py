#!/usr/bin/env python3
"""PREREG_RECIPE.md analysis. usage: analyze_recipe.py RAW_DIR | --self-test"""
import json, statistics as st, sys
from pathlib import Path


def analyze(p, n):
    def pps(s, k):
        v = [r["pps"] for r in p if r["cell"] == s and r["n"] == k and r["pps"]]
        return st.median(v) if len(v) == 3 else None
    def agg(s, k):
        return [r["agg_tps"] for r in n if r["cell"] == s and r["n"] == k and r["fail"] == 0]
    def per(s, k):
        return [x for r in n if r["cell"] == s and r["n"] == k and r["fail"] == 0 for x in r["per_stream"]]
    out = {s: {"pps_2k": pps(s, 2048), "pps_8k": pps(s, 8192), "agg": {k: agg(s, k) for k in (1, 2, 4)},
               "fails": sum(r["fail"] for r in n if r["cell"] == s)} for s in ("R1", "R2")}
    r1, r2 = out["R1"], out["R2"]
    one = r1["agg"][1] and st.median(per("R1", 1))
    out["Q1"] = {"holds": bool(r1["pps_8k"] and r1["pps_8k"] >= 365), "R1_8k": r1["pps_8k"]}
    out["Q2"] = {"holds": bool(one and one >= 25), "R1_1stream": one}
    t4, p2 = (st.median(r2["agg"][4]) if len(r2["agg"][4]) == 4 else None), (st.median(per("R2", 2)) if per("R2", 2) else None)
    out["Q3"] = {"holds": bool(t4 and p2 and t4 >= 46 and p2 >= 13), "R2_4stream_total": t4, "R2_2stream_per": p2}
    ok = []
    for s in ("R1", "R2"):
        v = r1["agg"][2] if s == "R1" else r2["agg"][2]
        ok.append(len(v) == 4 and min(v) >= 0.9 * st.median(v))
    out["Q4"] = {"holds": all(ok), "two_stream": {"R1": r1["agg"][2], "R2": r2["agg"][2]}}
    return out


def self_test():
    fails = []
    def check(m, c):
        print(("PASS  " if c else "FAIL  ") + m); fails.append(m) if not c else None
    p = [{"cell": s, "n": k, "rep": i, "pps": v + i} for s, v in (("R1", 380), ("R2", 428)) for k in (2048, 8192) for i in (1, 2, 3)]
    n = []
    for s, a in (("R1", {1: (26, [27.0]), 2: (40, [20.0, 20.0]), 4: (40, [10.0] * 4)}), ("R2", {1: (14, [14.3]), 2: (27, [13.5, 13.5]), 4: (48, [12.0] * 4)})):
        for ps in range(4):
            for k, (tot, ps_) in a.items():
                n.append({"cell": s, "pass": 1 + ps % 2, "n": k, "agg_tps": tot, "per_stream": ps_, "fail": 0})
    r = analyze(p, n)
    check("Q1 holds at 382", r["Q1"]["holds"] and r["Q1"]["R1_8k"] == 382)
    check("Q2 from per-stream (27.0)", r["Q2"]["holds"] and r["Q2"]["R1_1stream"] == 27.0)
    check("Q3 holds (48 total, 13.5 per)", r["Q3"]["holds"])
    check("Q4 holds when 2-stream is flat", r["Q4"]["holds"])
    n[1]["agg_tps"] = 25   # one R1 2-stream pass drops 37.5 %
    check("Q4 fails on a slow 2-stream pass", not analyze(p, n)["Q4"]["holds"])
    n2 = [dict(x, fail=1) if (x["cell"] == "R2" and x["n"] == 4) else x for x in n]
    check("Q3 fails when 4-stream requests fail", not analyze(p, n2)["Q3"]["holds"])
    print("self-test:", "FAILED" if fails else "all passed"); return 1 if fails else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    raw = Path(sys.argv[1])
    ld = lambda f: [json.loads(l) for l in open(raw / f) if l.strip()] if (raw / f).exists() else []
    print(json.dumps(analyze(ld("p_rows.jsonl"), ld("n_rows.jsonl")), indent=1, default=str))
