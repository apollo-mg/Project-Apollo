#!/usr/bin/env python3
"""PREREG_GLM_THREADS.md analysis. usage: analyze_glm_threads.py RAW_DIR | --self-test"""
import json, statistics as st, sys
from pathlib import Path


def med(rows, arm):
    v = [r["tps"] for r in rows if r["arm"] == arm and r["pass"] == 2 and r["tps"]]
    return st.median(v) if len(v) == 3 else None


def analyze(rows):
    m = {a: med(rows, a) for a in ("t20a", "t10", "t30", "t40", "t20b")}
    b = [x for x in (m["t20a"], m["t20b"]) if x]; base = sum(b) / len(b) if b else None
    others = [x for x in (m["t10"], m["t30"], m["t40"]) if x]
    return {"median_pass2": m, "t20_mean": base, "drift": (m["t20b"] / m["t20a"]) if m["t20a"] and m["t20b"] else None,
            "T1": {"holds": bool(base and others and max(others) >= 1.10 * base), "best_ratio": (max(others) / base) if base and others else None},
            "T2": {"holds": bool(base and m["t40"] and m["t40"] <= 1.02 * base), "t40_ratio": (m["t40"] / base) if base and m["t40"] else None},
            "T3": {"holds": bool(base and m["t10"] and m["t10"] <= 0.90 * base), "t10_ratio": (m["t10"] / base) if base and m["t10"] else None}}


def self_test():
    fails = []
    def check(m_, c):
        print(("PASS  " if c else "FAIL  ") + m_); fails.append(m_) if not c else None
    rows = [{"arm": a, "pass": ps, "prompt": i, "tps": v} for a, v in {"t20a": 4.7, "t10": 3.9, "t30": 5.3, "t40": 4.6, "t20b": 4.65}.items()
            for ps in (1, 2) for i in range(3)]
    r = analyze(rows)
    check("t20 mean 4.675", abs(r["t20_mean"] - 4.675) < 1e-9)
    check("T1 holds (5.3/4.675 = 1.134)", r["T1"]["holds"])
    check("T2 holds (4.6 <= 1.02x)", r["T2"]["holds"])
    check("T3 holds (3.9 <= 0.90x)", r["T3"]["holds"])
    check("missing arm -> no median", med([x for x in rows if x["arm"] != "t30" or x["prompt"]], "t30") is None)
    print("self-test:", "FAILED" if fails else "all passed"); return 1 if fails else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    print(json.dumps(analyze([json.loads(l) for l in open(Path(sys.argv[1]) / "rows.jsonl") if l.strip()]), indent=1))
