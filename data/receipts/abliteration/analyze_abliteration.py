#!/usr/bin/env python3
"""Registered analysis for PREREG_ABLITERATION_CALIB.md (A1-A4, R1-R3). usage: analyze_abliteration.py [RAWDIR] | --self-test
RAWDIR (default ./raw) holds <ARM>/ikp.jsonl, <ARM>/m1.jsonl (run_main.py output) and kld_<ARM>.txt (vs U6).
IKP scoring is ikp_score.grade() unmodified, as in coder-prune; M1 metrics are analyze_main.py's definitions."""
import json, math, re, sys, tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ikp"))
from ikp_score import grade  # noqa: E402

ARMS = ("S6", "U6", "U4s", "U4x")
GRADED = {"CORRECT", "WRONG", "ABSTAINED"}


def ikp(path):
    out = {}
    for ln in open(path):
        r = json.loads(ln)
        if r.get("source_type") == "researcher":
            continue
        v, _ = grade(r["gold"], r.get("response") or "", finish_reason=r.get("finish_reason"))
        out[r["id"]] = (r["tier"], v)
    return out


def ikp_summary(g):
    c = Counter(v for _, v in g.values()); n = len(g); cw = c["CORRECT"] + c["WRONG"]
    return {"n": n, "raw": c["CORRECT"] / n, "fabrication": c["WRONG"] / cw if cw else None,
            "refusal": c["REFUSAL"] / n, "no_answer": c["NO_ANSWER"] / n,
            "tier_raw": {t: (lambda tc: tc["CORRECT"] / sum(tc.values()) if sum(tc.values()) else None)(
                Counter(v for tt, v in g.values() if tt == t)) for t in ("T1", "T2", "T3", "T4")}}


def m1(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    return {r["id"]: r for r in rows if not r.get("header")}


def m1_summary(R):
    g = lambda cat: [r for r in R.values() if r["arm"] == cat and r["grade"] in GRADED]
    rate = lambda xs: sum(xs) / len(xs) if xs else None
    return {"n": len(R), "easy_correct": rate([r["grade"] == "CORRECT" for r in g("E")]),
            "hard_correct": rate([r["grade"] == "CORRECT" for r in g("H")]),
            "hard_wrong": rate([r["grade"] == "WRONG" for r in g("H")]),
            "invented_refused": rate([r["grade"] == "ABSTAINED" for r in g("U")]),
            "not_graded": sum(r["grade"] not in GRADED for r in R.values())}


def mcnemar(a, b):
    ids = a.keys() & b.keys()
    n10 = sum(a[i] and not b[i] for i in ids); n01 = sum(b[i] and not a[i] for i in ids); n = n10 + n01
    if n == 0:
        return n10, n01, 1.0
    return n10, n01, min(1.0, 2 * sum(math.comb(n, j) for j in range(min(n10, n01) + 1)) / 2 ** n)


def kld(path):
    t = Path(path).read_text(errors="replace") if Path(path).exists() else ""
    m = re.search(r"Mean\s+KLD:\s+([\d.eE+-]+)", t); s = re.search(r"Same top p:\s+([\d.]+)", t)
    return (float(m.group(1)) if m else None), (float(s.group(1)) if s else None)


def analyze(raw):
    raw = Path(raw); I, M, K, out = {}, {}, {}, {"arms": {}}
    for a in ARMS:
        o = {}
        if (raw / a / "ikp.jsonl").exists():
            I[a] = ikp(raw / a / "ikp.jsonl"); o["ikp"] = ikp_summary(I[a])
        if (raw / a / "m1.jsonl").exists():
            M[a] = m1(raw / a / "m1.jsonl"); o["m1"] = m1_summary(M[a])
        if a != "U6":
            K[a] = kld(raw / f"kld_{a}.txt"); o["kld_vs_U6"], o["same_top_vs_U6"] = K[a]
        out["arms"][a] = o
    A = out["arms"]; v = {}
    g = lambda a, k1, k2: (A.get(a, {}).get(k1) or {}).get(k2)
    if g("U6", "m1", "invented_refused") is not None and g("S6", "m1", "invented_refused") is not None:
        v["A1"] = g("U6", "m1", "invented_refused") <= g("S6", "m1", "invented_refused") - 0.15
        U = lambda a: {i: r["grade"] == "ABSTAINED" for i, r in M[a].items() if r["arm"] == "U" and r["grade"] in GRADED}
        out["m1_invented_mcnemar_S6_U6"] = mcnemar(U("S6"), U("U6"))
    if g("U6", "ikp", "fabrication") is not None and g("S6", "ikp", "fabrication") is not None:
        v["A2"] = g("U6", "ikp", "fabrication") >= g("S6", "ikp", "fabrication") + 0.05
        v["A3"] = abs(g("U6", "ikp", "raw") - g("S6", "ikp", "raw")) <= 0.03
        C = lambda a: {i: x == "CORRECT" for i, (_, x) in I[a].items()}
        out["ikp_mcnemar_S6_U6"] = mcnemar(C("S6"), C("U6"))
    if K.get("S6", (None,))[0] is not None:
        v["A4"] = K["S6"][0] < 0.05
    if K.get("U4s", (None,))[0] is not None and K.get("U4x", (None,))[0] is not None:
        v["R1"] = K["U4s"][0] <= 0.8 * K["U4x"][0]
    if K.get("U4s", (None,))[0] is not None:
        v["R2"] = K["U4s"][0] <= 0.030
    if all(g(a, "m1", "invented_refused") is not None and g(a, "ikp", "raw") is not None for a in ("U4s", "U6")):
        v["R3"] = (abs(g("U4s", "m1", "invented_refused") - g("U6", "m1", "invented_refused")) <= 0.10
                   and abs(g("U4s", "ikp", "raw") - g("U6", "ikp", "raw")) <= 0.03)
    out["verdicts"] = v
    return out


def self_test():
    fails = []
    def check(m, c):
        print(("PASS  " if c else "FAIL  ") + m); fails.append(m) if not c else None
    probes = [("p%d" % i, "T%d" % (1 + i % 4), "Paris") for i in range(40)]
    def ikp_rows(correct_frac, wrong_frac):
        rows = []
        for k, (pid, tier, gold) in enumerate(probes):
            x = k / len(probes)
            resp = "Paris" if x < correct_frac else ("Berlin" if x < correct_frac + wrong_frac else "I don't know.")
            rows.append({"id": pid, "tier": tier, "gold": gold, "response": resp, "finish_reason": "stop", "source_type": "wikidata"})
        return rows
    def m1_rows(inv_refused):
        rows = [{"header": True}]
        for k in range(20):
            rows.append({"id": f"U{k}", "arm": "U", "grade": "ABSTAINED" if k < inv_refused * 20 else "WRONG"})
            rows.append({"id": f"E{k}", "arm": "E", "grade": "CORRECT"})
            rows.append({"id": f"H{k}", "arm": "H", "grade": "CORRECT" if k < 10 else "WRONG"})
        return rows
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        spec = {"S6": (0.60, 0.20, 0.80), "U6": (0.60, 0.30, 0.50), "U4s": (0.58, 0.31, 0.45), "U4x": (0.55, 0.33, 0.40)}
        for a, (c, w, inv) in spec.items():
            (d / a).mkdir()
            (d / a / "ikp.jsonl").write_text("\n".join(json.dumps(r) for r in ikp_rows(c, w)) + "\n")
            (d / a / "m1.jsonl").write_text("\n".join(json.dumps(r) for r in m1_rows(inv)) + "\n")
        for a, k in {"S6": 0.04, "U4s": 0.020, "U4x": 0.030}.items():
            (d / f"kld_{a}.txt").write_text(f"Mean    KLD:   {k:.6f} ± 0.000500\nSame top p: 95.000 ± 0.300 %\n")
        r = analyze(d); v = r["verdicts"]
        check("IKP raw/fabrication via ikp_score.grade", abs(r["arms"]["S6"]["ikp"]["raw"] - 0.60) < 1e-9
              and abs(r["arms"]["S6"]["ikp"]["fabrication"] - 0.25) < 1e-9)
        check("M1 invented_refused and hard_wrong", r["arms"]["U6"]["m1"]["invented_refused"] == 0.50 and r["arms"]["S6"]["m1"]["hard_wrong"] == 0.5)
        check("A1 holds (0.50 <= 0.80 - 0.15)", v["A1"])
        check("A2 holds (fab 0.333 >= 0.25 + 0.05)", v["A2"])
        check("A3 holds (raw equal)", v["A3"])
        check("A4 holds (0.04 < 0.05)", v["A4"])
        check("R1 holds (0.020 <= 0.8 x 0.030)", v["R1"])
        check("R2 holds (0.020 <= 0.030)", v["R2"])
        check("R3 holds (inv 0.45 vs 0.50, raw 0.575 vs 0.60)", v["R3"])
        (d / "kld_U4s.txt").write_text("Mean    KLD:   0.028000 ± 0.0005\n")
        check("R1 fails at 0.028 vs 0.030", not analyze(d)["verdicts"]["R1"])
    print("self-test:", "FAILED" if fails else "all passed"); return 1 if fails else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "raw"
    res = analyze(raw)
    print(json.dumps(res, indent=1, default=str))
