#!/usr/bin/env python3
"""Score PREREG_MARKER_PENALTY_BONSAI.md (+ Deviation 1) -> RESULT_marker_bonsai.json.
Same statistics as analyze_marker.py (left unchanged so it still reproduces RESULT_marker.json), for one model whose
items were split across two testers: raw/out_bonsai1 (A1-A4, U1-U4) + raw/out_bonsai2 (A5-A8, U5-U8) are merged per
(arm, rep). Every item's arms ran on one tester, so each paired comparison stays within one instrument.
B1: C/A geometric-mean per-item thinking < 0.80 and exact sign-flip p < 0.05 over 16 items.
B2: NO-STOP (finish == length) count C < A (descriptive).
B3: answerable correct C >= A - 2 (of 24); unanswerable WRONG + NO-STOP C <= A + 2.
B4: answerable correct C >= A + 2.
Sensitivity (as in RESULT_MARKER_PENALTY.md): per-item means with finish == length rows excluded."""
import itertools, json
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
DIRS = ["out_bonsai1", "out_bonsai2"]
SIGNS = np.array(list(itertools.product((1, -1), repeat=16)), dtype=float)


def rows(arm):
    out = []
    for d in DIRS:
        for f in sorted((HERE / "raw" / d).glob(f"arm{arm}_rep*.jsonl")):
            rep = f.stem.split("_rep")[1]              # rows carry no seed field; the file names the rep
            out += [{**json.loads(l), "_rep": rep} for l in open(f) if l.strip()]
    return out


def perm(d):
    d = np.asarray(d, float)
    return float((np.abs((SIGNS * d).mean(1)) >= abs(d.mean()) - 1e-15).mean())


def think(r):
    return len(r.get("reasoning") or "")


D = {a: rows(a) for a in "ABC"}
items = sorted({r["id"] for r in D["A"]})
assert len(items) == 16 and all(len(D[a]) == 48 for a in "ABC"), [len(D[a]) for a in "ABC"]
for a in "ABC":   # one row per (item, rep): no duplicates from a resumed run
    assert len({(r["id"], r["_rep"]) for r in D[a]}) == 48, a
R = {"arms": {}}
for a in "ABC":
    ans = [r for r in D[a] if r["id"].startswith("CAL-A")]
    una = [r for r in D[a] if r["id"].startswith("CAL-U")]
    R["arms"][a] = {
        "answerable_correct": sum(r["status"] == "ANSWERED-CORRECT" for r in ans),
        "answerable_abstained": sum(r["status"] == "ABSTAINED" for r in ans),
        "answerable_no_stop": sum(r.get("finish") == "length" for r in ans),
        "unanswerable_abstained": sum(r["status"] == "ABSTAINED" and r.get("finish") != "length" for r in una),
        "unanswerable_wrong": sum(r["status"] == "ANSWERED-WRONG" and r.get("finish") != "length" for r in una),
        "unanswerable_no_stop": sum(r.get("finish") == "length" for r in una),
        "no_stop": sum(r.get("finish") == "length" for r in D[a]),
        "median_think_chars": float(np.median([think(r) for r in D[a]])),
        "median_think_unanswerable": float(np.median([think(r) for r in una])),
        "completion_tokens_total": sum(r.get("completion_tokens") or 0 for r in D[a]),
        "status_counts": {s: sum(r["status"] == s for r in D[a]) for s in sorted({r["status"] for r in D[a]})},
    }
    R["arms"][a]["unanswerable_fail"] = R["arms"][a]["unanswerable_wrong"] + R["arms"][a]["unanswerable_no_stop"]


def ratio(a, drop_length=False):
    m = {}
    for x in (a, "A"):
        m[x] = {}
        for i in items:
            v = [think(r) for r in D[x] if r["id"] == i and not (drop_length and r.get("finish") == "length")]
            m[x][i] = np.mean(v) if v else None
    its = [i for i in items if m[a][i] and m["A"][i]]
    d = [np.log(m[a][i] / m["A"][i]) for i in its]
    sg = np.array(list(itertools.product((1, -1), repeat=len(d))), dtype=float)
    p = float((np.abs((sg * np.asarray(d)).mean(1)) >= abs(np.mean(d)) - 1e-15).mean())
    una = [np.log(m[a][i] / m["A"][i]) for i in its if i.startswith("CAL-U")]
    return {"geo_ratio": float(np.exp(np.mean(d))), "p_perm": p, "n_items": len(its),
            "items_shorter": int(sum(x < 0 for x in d)),
            "unanswerable_only_ratio": float(np.exp(np.mean(una))) if una else None,
            "per_item_ratio": {i: round(float(m[a][i] / m["A"][i]), 3) for i in its}}


for a in "BC":
    R[f"{a}_vs_A"] = {**ratio(a), "no_length_rows": ratio(a, drop_length=True),
                      "answerable_correct_delta": R["arms"][a]["answerable_correct"] - R["arms"]["A"]["answerable_correct"],
                      "unanswerable_fail_delta": R["arms"][a]["unanswerable_fail"] - R["arms"]["A"]["unanswerable_fail"],
                      "no_stop_delta": R["arms"][a]["no_stop"] - R["arms"]["A"]["no_stop"]}
C = R["C_vs_A"]
R["B1"] = {"ratio": C["geo_ratio"], "p": C["p_perm"], "held": C["geo_ratio"] < 0.80 and C["p_perm"] < 0.05}
R["B2"] = {"no_stop_A": R["arms"]["A"]["no_stop"], "no_stop_C": R["arms"]["C"]["no_stop"],
           "held": R["arms"]["C"]["no_stop"] < R["arms"]["A"]["no_stop"]}
R["B3"] = {"ans_delta": C["answerable_correct_delta"], "una_fail_delta": C["unanswerable_fail_delta"],
           "held": C["answerable_correct_delta"] >= -2 and C["unanswerable_fail_delta"] <= 2}
R["B4"] = {"ans_delta": C["answerable_correct_delta"], "held": C["answerable_correct_delta"] >= 2}
(HERE / "RESULT_marker_bonsai.json").write_text(json.dumps(R, indent=1, default=float))
for a in "ABC":
    x = R["arms"][a]
    print(f"{a}: ans ok {x['answerable_correct']}/24 (abst {x['answerable_abstained']}, no-stop {x['answerable_no_stop']})  "
          f"una: abst {x['unanswerable_abstained']} wrong {x['unanswerable_wrong']} no-stop {x['unanswerable_no_stop']}  "
          f"median think {x['median_think_chars']:.0f} (una {x['median_think_unanswerable']:.0f})  tok {x['completion_tokens_total']}")
for a in "BC":
    y = R[f"{a}_vs_A"]
    print(f"{a} vs A: ratio {y['geo_ratio']:.3f} p {y['p_perm']:.4f} shorter {y['items_shorter']}/16 una-only "
          f"{y['unanswerable_only_ratio']:.3f} | no-length-rows ratio {y['no_length_rows']['geo_ratio']:.3f} "
          f"p {y['no_length_rows']['p_perm']:.4f} (n {y['no_length_rows']['n_items']}) | ans d {y['answerable_correct_delta']:+d} "
          f"una-fail d {y['unanswerable_fail_delta']:+d} no-stop d {y['no_stop_delta']:+d}")
for k in ("B1", "B2", "B3", "B4"):
    print(k, R[k])
