#!/usr/bin/env python3
"""Registered analysis for PREREG_FLASHNEXT_STOPPING.md (committed before any Flash-Next stopping row existed).
Per arm: answerable ANSWERED-CORRECT /24; unanswerable ABSTAINED, ANSWERED-WRONG, NO-STOP/REC /24; total NO-STOP;
median reasoning chars. Reference: the 27B Q6_K arm A (overthink_q6k). Predictions B1-B4 exactly as registered.
Usage: analyze_flashnext_stopping.py [--q2 DIR] [--iq4 DIR] [--ref DIR]   (dirs holding armA_rep{1,2,3}.jsonl)"""
import argparse, glob, json, statistics as st
from pathlib import Path
H = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--q2", default=str(H / "flashnext_stop" / "FNQ2")); ap.add_argument("--iq4", default=str(H / "flashnext_stop" / "FNIQ4"))
ap.add_argument("--ref", default=str(H / "overthink_q6k"))
a = ap.parse_args()
def load(d):
    rows = []
    for f in sorted(glob.glob(str(Path(d) / "armA_rep*.jsonl"))):
        rows += [json.loads(l) for l in open(f) if l.strip()]
    return rows
S = {}
for k, d in (("FNQ2", a.q2), ("FNIQ4", a.iq4), ("27B-Q6K", a.ref)):
    r = load(d)
    A = [x for x in r if x["arm"] == "answerable"]; U = [x for x in r if x["arm"] == "unanswerable"]
    s = {"n": len(r), "A_correct": sum(x["status"] == "ANSWERED-CORRECT" for x in A), "nA": len(A),
         "U_abstain": sum(x["status"] == "ABSTAINED" for x in U), "U_wrong": sum(x["status"] == "ANSWERED-WRONG" for x in U),
         "nostop": sum(x["status"].startswith("NO-STOP") for x in r), "nU": len(U),
         "other": sum(x["status"] not in ("ANSWERED-CORRECT", "ABSTAINED", "ANSWERED-WRONG") and not x["status"].startswith("NO-STOP") for x in r),
         "med_reason": st.median([len(x.get("reasoning") or "") for x in r] or [0])}
    S[k] = s
    print(f"{k:8s} n={s['n']:2d}  answerable {s['A_correct']}/{s['nA']}  unanswerable abstain {s['U_abstain']}/{s['nU']} wrong {s['U_wrong']}  "
          f"NO-STOP {s['nostop']}  other {s['other']}  median reasoning {s['med_reason']:.0f} ch")
res = {}
if S["FNQ2"]["n"] == 48 and S["FNIQ4"]["n"] == 48:
    res["B1"] = S["FNQ2"]["nostop"] <= S["FNIQ4"]["nostop"] + 2
if S["FNQ2"]["n"] == 48:
    res["B2"] = S["FNQ2"]["nostop"] <= S["27B-Q6K"]["nostop"] + 2
    res["B3"] = S["FNQ2"]["U_abstain"] >= S["27B-Q6K"]["U_abstain"] - 2
    res["B4"] = S["FNQ2"]["A_correct"] >= 22
for k, v in res.items():
    print(k, "HOLDS" if v else "does not hold")
