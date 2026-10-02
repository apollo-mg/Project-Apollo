#!/usr/bin/env python3
"""PREREG_GLM_NUMA.md analysis. usage: analyze_glm_numa.py RAW_DIR | --self-test"""
import json, re, statistics as st, sys, tempfile
from pathlib import Path


def med(rows, arm, ps=2):
    v = [r["tps"] for r in rows if r["arm"] == arm and r["pass"] == ps and r["tps"]]
    return st.median(v) if len(v) == 3 else None


def node_split(txt):
    """numastat -p 'Total' line -> (node0 MB, node1 MB)"""
    m = re.search(r"^Total\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", txt, re.M)
    return (float(m.group(1)), float(m.group(2))) if m else None


def analyze(rows, numa):
    m = {a: med(rows, a) for a in ("M", "B1", "D", "I", "B2")}
    p1 = {a: med(rows, a, 1) for a in m}
    b = [x for x in (m["B1"], m["B2"]) if x]
    bmean = sum(b) / len(b) if b else None
    s = numa.get("B1")
    share = max(s) / sum(s) if s else None
    out = {"median_pass2": m, "median_pass1": p1, "B_mean": bmean,
           "drift_B1_B2": (m["B2"] / m["B1"]) if m["B1"] and m["B2"] else None,
           "G1": {"holds": bool(m["I"] and bmean and m["I"] >= 1.15 * bmean), "ratio": (m["I"] / bmean) if m["I"] and bmean else None},
           "G2": {"holds": bool(share and share >= 0.70), "B1_max_node_share": share},
           "G3": {"holds": bool(m["D"] and bmean and m["I"] and m["D"] >= 1.05 * bmean and m["I"] >= m["D"]),
                  "D_ratio": (m["D"] / bmean) if m["D"] and bmean else None},
           "node_split_MB": numa}
    return out


def self_test():
    fails = []
    def check(n, c):
        print(("PASS  " if c else "FAIL  ") + n); fails.append(n) if not c else None
    rows = [{"arm": a, "pass": ps, "prompt": i, "tps": v + (0.1 * i if ps == 2 else -0.5)}
            for a, v in {"M": 4.4, "B1": 4.5, "D": 4.9, "I": 5.6, "B2": 4.6}.items() for ps in (1, 2) for i in range(3)]
    numa = {"B1": node_split("Total   52000.0   8000.0   60000.0\n"), "I": node_split("Total 30000 30000 60000\n")}
    r = analyze(rows, numa)
    check("B mean of pass-2 medians", abs(r["B_mean"] - 4.65) < 1e-9)
    check("G1 holds at 5.7/4.65", r["G1"]["holds"])
    check("G2 holds at 52/60 on one node", r["G2"]["holds"] and abs(r["G2"]["B1_max_node_share"] - 52 / 60) < 1e-9)
    check("G3 holds (D 5.0 >= 1.05x, I >= D)", r["G3"]["holds"])
    check("pass 1 kept separate", r["median_pass1"]["I"] == 5.1)
    rows2 = [dict(x, tps=x["tps"] * (0.8 if x["arm"] == "I" else 1)) for x in rows]
    check("G1 fails when I is not 1.15x", not analyze(rows2, numa)["G1"]["holds"])
    check("an arm with 2 rows has no median", med([x for x in rows if not (x["arm"] == "D" and x["prompt"] == 0)], "D") is None)
    print("self-test:", "FAILED" if fails else "all passed"); return 1 if fails else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    raw = Path(sys.argv[1])
    rows = [json.loads(l) for l in open(raw / "rows.jsonl") if l.strip()]
    numa = {p.stem[5:]: node_split(p.read_text()) for p in raw.glob("numa_*.txt")}
    print(json.dumps(analyze(rows, numa), indent=1))
