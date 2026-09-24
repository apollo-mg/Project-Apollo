#!/usr/bin/env python3
"""Score PREREG_REAP_FLASHNEXT.md from raw/<ARM>/{ikp.jsonl, hep_results_t0.0_k1.json}.

Primary: ikp_score.grade() UNMODIFIED (length-truncated -> NO_ANSWER), --exclude-source researcher.
  raw = CORRECT / all;  committed = CORRECT / (CORRECT + WRONG);  fabrication = WRONG / (CORRECT + WRONG)
Post-hoc sensitivity (declared, not registered): grade truncated rows on their content
  (finish_reason passed as None), because Flash-Next appends explanation and hits the 64-token cap.
Paired exact McNemar (two-sided) per comparison: per-probe CORRECT for IKP, per-problem PASS for HEP.
"""
import json, math, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ikp"))
from ikp_score import grade  # noqa: E402

ARMS = ["FULLQ2", "R320Q2", "R320Q3", "IQ1S", "D27Q6"]
EXCL = {"researcher"}


def ikp(arm, truncated_as_stop=False):
    out = {}
    for ln in open(HERE / "raw" / arm / "ikp.jsonl"):
        r = json.loads(ln)
        if r.get("source_type") in EXCL:
            continue
        fr = None if truncated_as_stop else r.get("finish_reason")
        v, _ = grade(r["gold"], r.get("response") or "", finish_reason=fr)
        out[r["id"]] = (r["tier"], v)
    return out


def hep(arm):
    d = json.load(open(HERE / "raw" / arm / "hep_results_t0.0_k1.json"))
    return {x["task_id"]: bool(x["passes"][0]) for x in d["results"]}, Counter(b for x in d["results"] for b in x["buckets"])


def mcnemar(a, b):  # a, b: dict id -> bool; exact two-sided binomial on discordant pairs
    ids = a.keys() & b.keys()
    n10 = sum(a[i] and not b[i] for i in ids); n01 = sum(b[i] and not a[i] for i in ids)
    n = n10 + n01
    if n == 0:
        return n10, n01, 1.0
    k = min(n10, n01)
    p = min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n)
    return n10, n01, p


def summary(g):
    c = Counter(v for _, v in g.values()); n = len(g)
    cw = c["CORRECT"] + c["WRONG"]
    t1 = Counter(v for t, v in g.values() if t == "T1")
    return {"n": n, "raw": c["CORRECT"] / n, "committed": c["CORRECT"] / cw if cw else None,
            "fabrication": c["WRONG"] / cw if cw else None, "refusal": c["REFUSAL"] / n,
            "no_answer": c["NO_ANSWER"] / n, "ambiguous": c["AMBIGUOUS"] / n,
            "T1_committed": t1["CORRECT"] / (t1["CORRECT"] + t1["WRONG"]) if (t1["CORRECT"] + t1["WRONG"]) else None}


res = {"primary": {}, "posthoc_truncated_graded": {}, "hep": {}, "tests": {}}
G = {a: ikp(a) for a in ARMS}
GP = {a: ikp(a, True) for a in ARMS}
H = {}
for a in ARMS:
    res["primary"][a] = summary(G[a]); res["posthoc_truncated_graded"][a] = summary(GP[a])
    H[a], buckets = hep(a)
    res["hep"][a] = {"pass@1": sum(H[a].values()) / len(H[a]), "buckets": dict(buckets)}

corr = lambda g: {i: v == "CORRECT" for i, (t, v) in g.items()}
for name, (x, y) in {"C1_prune_cost (R320Q2 vs FULLQ2)": ("R320Q2", "FULLQ2"),
                     "C2_prune_vs_quantize (R320Q3 vs IQ1S)": ("R320Q3", "IQ1S"),
                     "C3_dense27B_vs_FULLQ2": ("D27Q6", "FULLQ2"),
                     "C3_dense27B_vs_R320Q3": ("D27Q6", "R320Q3"),
                     "C3_dense27B_vs_IQ1S": ("D27Q6", "IQ1S"),
                     "quant_cost_at_K320 (R320Q2 vs R320Q3)": ("R320Q2", "R320Q3")}.items():
    res["tests"][name] = {"ikp_only_first_correct, only_second, p": mcnemar(corr(G[x]), corr(G[y])),
                          "ikp_posthoc": mcnemar(corr(GP[x]), corr(GP[y])),
                          "hep": mcnemar(H[x], H[y])}

(HERE / "RESULT_reapfn.json").write_text(json.dumps(res, indent=1))
f = lambda v: "   -  " if v is None else f"{100*v:5.1f}%"
print("PRIMARY (ikp_score unmodified)      raw  commit   fabr  refus  noans  ambig  T1comm | HEP pass@1")
for a in ARMS:
    s, h = res["primary"][a], res["hep"][a]
    print(f"{a:7s} {f(s['raw'])} {f(s['committed'])} {f(s['fabrication'])} {f(s['refusal'])} {f(s['no_answer'])} "
          f"{f(s['ambiguous'])} {f(s['T1_committed'])} | {f(h['pass@1'])}  {h['buckets']}")
print("POST-HOC (truncated rows graded on content)")
for a in ARMS:
    s = res["posthoc_truncated_graded"][a]
    print(f"{a:7s} {f(s['raw'])} {f(s['committed'])} {f(s['fabrication'])} {f(s['refusal'])} {f(s['no_answer'])} {f(s['ambiguous'])}")
print("TESTS (only-first, only-second, exact McNemar p)")
for k, v in res["tests"].items():
    print(f"  {k:40s} ikp {v['ikp_only_first_correct, only_second, p']}  posthoc {v['ikp_posthoc']}  hep {v['hep']}")
