#!/usr/bin/env python3
"""PREREG_NUMA_PREFILL.md analysis. usage: analyze_numa_pf.py RAW_DIR | --self-test"""
import json, statistics as st, sys, tempfile
from pathlib import Path

ARM = {"U": ["U1", "U2", "U3"], "C0": ["C0a", "C0b"], "C1": ["C1a", "C1b"]}
NODE0 = set(range(0, 10)) | set(range(20, 30))


def two_stream(rows, tag):
    return [r["agg_tps"] for r in rows if r["cell"] == tag and r["n"] == 2]   # file order = pass order (4 per start)


def part_n(rows):
    v = {a: [x for t in tags for x in two_stream(rows, t)] for a, tags in ARM.items()}
    med = {a: st.median(x) for a, x in v.items() if x}
    within = {a: max(abs(x / med[a] - 1) for x in v[a]) for a in ("C0", "C1") if v.get(a)}
    u = v.get("U", [])
    return {"two_stream": v, "median": med, "max_dev_bound": within,
            "N1": {"holds": len(within) == 2 and all(d <= 0.05 for d in within.values()) and all(len(v[a]) == 8 for a in ("C0", "C1"))},
            "N2": {"holds": len(u) == 12 and max(u) / min(u) >= 1.15, "u_max_over_min": (max(u) / min(u)) if u else None},
            "N3": {"holds": "C0" in med and "C1" in med and abs(med["C0"] / med["C1"] - 1) >= 0.10,
                   "c0_over_c1": (med["C0"] / med["C1"]) if "C0" in med and "C1" in med else None}}


def node0_frac(path):
    s = [int(x) for l in Path(path).read_text().splitlines() for x in l.split()] if Path(path).exists() else []
    return (sum(c in NODE0 for c in s) / len(s)) if s else None


def part_p(rows):
    med = {}
    for r in rows:
        med.setdefault((r["cell"], r["n"]), []).append(r["pps"])
    m = {k: st.median(v) for k, v in med.items() if len(v) == 3 and all(v)}
    g = lambda c, n=8192: m.get((c, n))
    out = {"median_pps": {f"{c}@{n}": round(x, 1) for (c, n), x in sorted(m.items())}}
    out["P1"] = {"holds": bool(g("T512") and g("L512") and g("T512") > g("L512")), "T512": g("T512"), "L512": g("L512")}
    out["P2"] = {"holds": bool(g("T2048") and g("T512") and g("T2048") >= 1.15 * g("T512")),
                 "ratio": (g("T2048") / g("T512")) if g("T2048") and g("T512") else None}
    out["P3"] = {"holds": bool(g("L2048") and g("L512") and g("L2048") < 1.15 * g("L512")),
                 "ratio": (g("L2048") / g("L512")) if g("L2048") and g("L512") else None}
    best = max((x for (c, n), x in m.items() if n == 8192), default=None)
    out["P4"] = {"holds": bool(best and best >= 163), "best_8k": best}
    return out


def self_test():
    fails = []
    def check(name, c):
        print(("PASS  " if c else "FAIL  ") + name); fails.append(name) if not c else None
    rows = []
    for tag, vals in {"U1": [30, 19, 30, 19], "U2": [20, 20, 21, 20], "U3": [29, 29, 30, 30],
                      "C0a": [30, 30.5, 29.8, 30], "C0b": [30.2, 30, 29.9, 30.1], "C1a": [25, 25.4, 25, 24.8], "C1b": [25, 25.1, 25, 25]}.items():
        for i, x in enumerate(vals):
            for n in (1, 2, 4):
                rows.append({"cell": tag, "pass": 1 + i % 2, "n": n, "agg_tps": x if n == 2 else 99})
    r = part_n(rows)
    check("N1 holds: bound arms within 5 %", r["N1"]["holds"])
    check("N2 holds: U spread 30/19", r["N2"]["holds"] and abs(r["N2"]["u_max_over_min"] - 30 / 19) < 1e-9)
    check("N3 holds: C0 vs C1 differ ~20 %", r["N3"]["holds"])
    rows2 = [dict(x, agg_tps=x["agg_tps"] * (1.08 if x["cell"] == "C0b" and x["n"] == 2 else 1)) for x in rows]
    check("N1 fails when one bound start sits 8 % off", not part_n(rows2)["N1"]["holds"])
    prow = []
    for c, base in {"L512": 120, "L2048": 125, "L4096": 110, "T512": 140, "T2048": 175, "T4096": 180}.items():
        for n in (2048, 8192):
            for rep in (1, 2, 3):
                prow.append({"cell": c, "n": n, "rep": rep, "pps": base + rep})
    p = part_p(prow)
    check("P1 holds (T512 > L512)", p["P1"]["holds"])
    check("P2 holds (T2048/T512 = 177/142)", p["P2"]["holds"])
    check("P3 holds (L2048/L512 < 1.15)", p["P3"]["holds"])
    check("P4 holds (best 182 >= 163)", p["P4"]["holds"] and p["P4"]["best_8k"] == 182)
    check("a cell with a missing rep is excluded", part_p(prow[:-1])["P4"]["best_8k"] == 177)
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "psr.txt"; f.write_text("3 4\n12\n\n25 31\n")
        check("node-0 fraction from psr samples (3,4,25 of 3,4,12,25,31)", abs(node0_frac(f) - 3 / 5) < 1e-9)
    print("self-test:", "FAILED" if fails else "all passed")
    return 1 if fails else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    raw = Path(sys.argv[1]); out = {}
    if (raw / "n_rows.jsonl").exists():
        out["N"] = part_n([json.loads(l) for l in open(raw / "n_rows.jsonl") if l.strip()])
        out["N"]["node0_frac"] = {p.stem: node0_frac(p) for p in sorted(raw.glob("psr_*.txt"))}
    if (raw / "p_rows.jsonl").exists():
        out["P"] = part_p([json.loads(l) for l in open(raw / "p_rows.jsonl") if l.strip()])
    print(json.dumps(out, indent=1, default=str))
