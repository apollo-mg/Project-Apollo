#!/usr/bin/env python3
"""Registered analysis for PREREG_CODER_PRUNE.md (committed before any row). C1-C4 exactly as registered.
Scoring functions copied verbatim from reap-flashnext/analyze_reapfn.py (ikp_score.grade unmodified; primary grades
length-truncated rows NO_ANSWER; post-hoc grades them on content). usage: analyze_coder.py [RAWDIR CODER_ARM BASE_ARM]
(args only for the self-test on REAP's stored arms)."""
import json, math, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ikp"))
from ikp_score import grade  # noqa: E402

RAW = Path(sys.argv[1]) if len(sys.argv) > 3 else HERE / "raw"
CA, BA = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("CODER", "FNGB")
EXCL = {"researcher"}
REAP_DROP = -0.198


def ikp(arm, truncated_as_stop=False):
    out = {}
    for ln in open(RAW / arm / "ikp.jsonl"):
        r = json.loads(ln)
        if r.get("source_type") in EXCL:
            continue
        fr = None if truncated_as_stop else r.get("finish_reason")
        v, _ = grade(r["gold"], r.get("response") or "", finish_reason=fr)
        out[r["id"]] = (r["tier"], v)
    return out


def hep(arm):
    d = json.load(open(RAW / arm / "hep_results_t0.0_k1.json"))
    return {x["task_id"]: bool(x["passes"][0]) for x in d["results"]}


def mcnemar(a, b):
    ids = a.keys() & b.keys()
    n10 = sum(a[i] and not b[i] for i in ids); n01 = sum(b[i] and not a[i] for i in ids)
    n = n10 + n01
    if n == 0:
        return n10, n01, 1.0
    k = min(n10, n01)
    return n10, n01, min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n)


def summary(g):
    c = Counter(v for _, v in g.values()); n = len(g); cw = c["CORRECT"] + c["WRONG"]
    tiers = {t: Counter(v for tt, v in g.values() if tt == t) for t in ("T1", "T2", "T3", "T4")}
    return {"n": n, "raw": c["CORRECT"] / n, "committed": c["CORRECT"] / cw if cw else None,
            "fabrication": c["WRONG"] / cw if cw else None, "refusal": c["REFUSAL"] / n, "no_answer": c["NO_ANSWER"] / n,
            "tier_raw": {t: (tc["CORRECT"] / sum(tc.values()) if sum(tc.values()) else None) for t, tc in tiers.items()}}


def main():
    res, out = {}, {}
    have = lambda a, f: (RAW / a / f).exists()
    corr = lambda g: {i: v == "CORRECT" for i, (t, v) in g.items()}
    S = {}
    for a in (CA, BA):
        if have(a, "ikp.jsonl"):
            S[a] = (ikp(a), ikp(a, True))
            out[a] = {"primary": summary(S[a][0]), "posthoc": summary(S[a][1])}
    f = lambda v: "   -  " if v is None else f"{100 * v:5.1f}%"
    for a, o in out.items():
        for kind in ("primary", "posthoc"):
            s = o[kind]
            print(f"{a:6s} {kind:8s} raw {f(s['raw'])} committed {f(s['committed'])} fabrication {f(s['fabrication'])} "
                  f"refusal {f(s['refusal'])} no-answer {f(s['no_answer'])} | T1 {f(s['tier_raw']['T1'])} T2 {f(s['tier_raw']['T2'])} "
                  f"T3 {f(s['tier_raw']['T3'])} T4 {f(s['tier_raw']['T4'])}  (n={s['n']})")
    if CA in S and BA in S:
        d = out[CA]["primary"]["raw"] - out[BA]["primary"]["raw"]
        m = mcnemar(corr(S[CA][0]), corr(S[BA][0]))
        mp = mcnemar(corr(S[CA][1]), corr(S[BA][1]))
        print(f"IKP {CA} - {BA}: {100 * d:+.1f} pp; only-{CA}, only-{BA}, p = {m}; post-hoc {100 * (out[CA]['posthoc']['raw'] - out[BA]['posthoc']['raw']):+.1f} pp {mp}")
        res["C1"] = d <= -0.10 and m[2] < 0.01
        fa, fb = out[CA]["primary"]["fabrication"], out[BA]["primary"]["fabrication"]
        res["C2"] = fa is not None and fb is not None and fa >= fb + 0.15
        res["C3"] = d > REAP_DROP
        print(f"fabrication {CA} {f(fa)} vs {BA} {f(fb)}; REAP-320 drop vs its parent {100 * REAP_DROP:+.1f} pp")
        res["ikp"] = {"delta_raw": d, "mcnemar": m, "mcnemar_posthoc": mp}
    if have(CA, "hep_results_t0.0_k1.json") and have(BA, "hep_results_t0.0_k1.json"):
        ha, hb = hep(CA), hep(BA)
        pa, pb = sum(ha.values()) / len(ha), sum(hb.values()) / len(hb)
        res["C4"] = abs(pa - pb) <= 0.05
        print(f"HumanEval+ {CA} {f(pa)} vs {BA} {f(pb)} ({100 * (pa - pb):+.1f} pp), McNemar {mcnemar(ha, hb)}")
        res["hep"] = {CA: pa, BA: pb}
    for k in ("C1", "C2", "C3", "C4"):
        print(k, ("HOLDS" if res[k] else "does not hold") if k in res else "pending")
    if len(sys.argv) <= 3:
        json.dump({"verdicts": {k: v for k, v in res.items() if k.startswith("C")}, "arms": out, **{k: v for k, v in res.items() if not k.startswith("C")}},
                  open(HERE / "RESULT_coder.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
