#!/usr/bin/env python3
"""Registered analysis for PREREG_SWIFT_FLASHNEXT.md (committed before any row). F1-F5 exactly as registered.
Stage 1: M1 rates for FNGB (base) and FNGS (Swift), paired bootstrap over items (10,000 resamples, seed 20260929).
Stage 2: CAL xhigh counts, median reasoning chars, Fisher exact p (reported). Speed: median decode tok/s and pooled
acceptance per arm x MTP. Unpredicted: FNGB vs base UD-Q2_K_XL (Stage A main_FNQ2, Stage B FNQ2).
usage: analyze_swift_flashnext.py [BASE SWIFT CALDIR]   (args only for the self-test on stored arms)"""
import glob, json, statistics as st, sys
from pathlib import Path
import numpy as np
from scipy.stats import fisher_exact

H = Path(__file__).resolve().parent; QA = H.parent / "quant-abstention"
BA, SA = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("FNGB", "FNGS")
CALDIR = Path(sys.argv[3]) if len(sys.argv) > 3 else H / "swift_flashnext"
items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}


def m1(arm):
    p = QA / "raw" / f"main_{arm}.jsonl"
    if not p.exists():
        return {}
    return {r["id"]: r for r in (json.loads(l) for l in list(open(p))[1:]) if "id" in r}


def cal(d, arm):
    rows = []
    for f in sorted(glob.glob(str(d / arm / "armA_rep*.jsonl"))):
        rows += [json.loads(l) for l in open(f) if l.strip()]
    return rows


def cal_stats(rows):
    U = [x for x in rows if x["arm"] == "unanswerable"]; A = [x for x in rows if x["arm"] == "answerable"]
    wb = sum(x["status"] == "ANSWERED-WRONG" and x.get("id") == "CAL-A2" and "weber" in (x.get("got") or "").lower()
             for x in A)
    return {"n": len(rows), "A": sum(x["status"] == "ANSWERED-CORRECT" for x in A), "A_afm51": wb,
            "Uab": sum(x["status"] == "ABSTAINED" for x in U), "Uwr": sum(x["status"] == "ANSWERED-WRONG" for x in U),
            "nostop": sum(x["status"].startswith("NO-STOP") for x in rows),
            "Umed": st.median([len(x.get("reasoning") or "") for x in U] or [0]),
            "Amed": st.median([len(x.get("reasoning") or "") for x in A] or [0]),
            "tok_med": st.median([x.get("completion_tokens") or 0 for x in rows] or [0])}


res, out = {}, {}
b, s = m1(BA), m1(SA)
ids = sorted(set(items) & set(b) & set(s))
if ids:
    rng = np.random.default_rng(20260929)
    rate = lambda R, grp, grade: float(np.mean([R[i]["grade"] == grade for i in ids if items[i]["arm"] == grp]))

    def boot(grp, grade):
        g = [i for i in ids if items[i]["arm"] == grp]
        d = np.array([(s[i]["grade"] == grade) - (b[i]["grade"] == grade) for i in g], float)
        m = d[rng.integers(0, len(d), (10000, len(d)))].mean(1)
        return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))

    print(f"M1 n={len(ids)}")
    for name, R in ((f"base {BA}", b), (f"Swift {SA}", s)):
        print(f"  {name}: E {rate(R, 'E', 'CORRECT'):.2f}  H {rate(R, 'H', 'CORRECT'):.2f}  U refused {rate(R, 'U', 'ABSTAINED'):.2f}")
    du, duci = boot("U", "ABSTAINED"); dh, dhci = boot("H", "CORRECT")
    same = sum(b[i]["grade"] == s[i]["grade"] for i in ids)
    print(f"  Swift - base: U refused {du:+.3f} [{duci[0]:+.3f}, {duci[1]:+.3f}]  H correct {dh:+.3f} [{dhci[0]:+.3f}, {dhci[1]:+.3f}]"
          f"  same grade {same}/{len(ids)}")
    res["F1"] = duci[0] <= 0; res["F2"] = dhci[0] <= 0 <= dhci[1]
    out["m1"] = {"du": du, "duci": duci, "dh": dh, "dhci": dhci, "same_grade": same, "n": len(ids)}
    ref = m1("FNQ2")
    if ref and not sys.argv[1:]:
        print(f"  [unpredicted] base UD-Q2_K_XL FNQ2 (Stage A, cross-session): E {rate(ref, 'E', 'CORRECT'):.2f}  "
              f"H {rate(ref, 'H', 'CORRECT'):.2f}  U refused {rate(ref, 'U', 'ABSTAINED'):.2f}")

C = {arm: cal_stats(cal(CALDIR, arm)) for arm in (BA, SA)}
for arm, c in C.items():
    print(f"CAL {arm}: n={c['n']} answerable {c['A']}/24 (+{c['A_afm51']} AFM-51)  unanswerable abstained {c['Uab']}/24 "
          f"wrong {c['Uwr']}  NO-STOP {c['nostop']}  median reasoning U {c['Umed']:.0f} / A {c['Amed']:.0f} ch  "
          f"median completion {c['tok_med']:.0f} tok")
if C[BA]["n"] == 48 and C[SA]["n"] == 48:
    res["F3"] = C[SA]["Umed"] <= 0.8 * C[BA]["Umed"]; res["F4"] = C[SA]["Uab"] <= C[BA]["Uab"]
    p = fisher_exact([[C[SA]["Uab"], 24 - C[SA]["Uab"]], [C[BA]["Uab"], 24 - C[BA]["Uab"]]])[1]
    print(f"  Swift/base unanswerable reasoning {C[SA]['Umed'] / max(C[BA]['Umed'], 1):.2f}x; abstained Fisher p={p:.3f} (reported)")
if not sys.argv[1:]:
    q2 = cal_stats(cal(H / "flashnext_stop", "FNQ2"))
    print(f"  [unpredicted] base UD-Q2_K_XL FNQ2 (Stage B): answerable {q2['A']}/24  abstained {q2['Uab']}/24  "
          f"NO-STOP {q2['nostop']}  median reasoning U {q2['Umed']:.0f} ch")
out["cal"] = C

sp = CALDIR / "speed.jsonl"
if sp.exists():
    rows = [json.loads(l) for l in open(sp) if l.strip()]
    S = {}
    for arm in (BA, SA):
        for m in ("off", "on"):
            r = [x for x in rows if x["arm"] == arm and x["mtp"] == m]
            if not r:
                continue
            dn = sum(x.get("draft_n") or 0 for x in r); da = sum(x.get("draft_n_accepted") or 0 for x in r)
            S[(arm, m)] = {"n": len(r), "tps": st.median([x["predicted_per_second"] for x in r]), "acc": da / dn if dn else None}
            print(f"speed {arm} MTP {m}: n={len(r)} median decode {S[(arm, m)]['tps']:.2f} tok/s"
                  + (f"  acceptance {S[(arm, m)]['acc']:.3f}" if dn else ""))
        if (arm, "off") in S and (arm, "on") in S:
            print(f"  {arm} MTP speedup {S[(arm, 'on')]['tps'] / S[(arm, 'off')]['tps']:.2f}x")
    if S.get((BA, "on"), {}).get("acc") is not None and S.get((SA, "on"), {}).get("acc") is not None:
        res["F5"] = S[(SA, "on")]["acc"] >= S[(BA, "on")]["acc"] - 0.10
    for arm in (BA, SA):   # time to answer estimate: median completion tokens / decode rate
        for m in ("off", "on"):
            if (arm, m) in S and C[arm]["n"]:
                print(f"  est. CAL time to answer {arm} MTP {m}: {C[arm]['tok_med'] / S[(arm, m)]['tps']:.0f} s (median)")
    out["speed"] = {f"{a}|{m}": v for (a, m), v in S.items()}

for k in ("F1", "F2", "F3", "F4", "F5"):
    print(k, ("HOLDS" if res[k] else "does not hold") if k in res else "pending")
if not sys.argv[1:]:
    json.dump({"verdicts": res, **out}, open(H / "RESULT_swift_flashnext.json", "w"), indent=1, default=str)
