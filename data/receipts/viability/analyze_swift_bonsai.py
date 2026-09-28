#!/usr/bin/env python3
"""Registered analysis for PREREG_SWIFT_BONSAI.md (committed before any row). Stage 1: M1 rates for BONB9 (base) and
SWB9 (Swift), paired bootstrap over items (10,000 resamples, seed 20260928). Stage 2: CAL xhigh counts and median
reasoning chars. S1-S4 exactly as registered."""
import glob, json, statistics as st
from pathlib import Path
import numpy as np
H = Path(__file__).resolve().parent; QA = H.parent / "quant-abstention"
items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
def m1(arm):
    rows = [json.loads(l) for l in open(QA / "raw" / f"main_{arm}.jsonl")][1:]
    return {r["id"]: r for r in rows if "id" in r}
import sys
BA, SA = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("BONB9", "SWB9")   # arm names; args only for the self-test
b, s = m1(BA), m1(SA)
ids = sorted(set(items) & set(b) & set(s))
rng = np.random.default_rng(20260928)
def rate(R, grp, grade): return np.mean([R[i]["grade"] == grade for i in ids if items[i]["arm"] == grp])
def boot(grp, grade):
    g = [i for i in ids if items[i]["arm"] == grp]
    d = np.array([(s[i]["grade"] == grade) - (b[i]["grade"] == grade) for i in g], float)
    m = d[rng.integers(0, len(d), (10000, len(d)))].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))
print(f"M1 n={len(ids)}")
for name, R in (("base BONB9", b), ("Swift SWB9", s)):
    print(f"  {name}: E {rate(R, 'E', 'CORRECT'):.2f}  H {rate(R, 'H', 'CORRECT'):.2f}  U refused {rate(R, 'U', 'ABSTAINED'):.2f}")
du, duci = boot("U", "ABSTAINED"); dh, dhci = boot("H", "CORRECT")
print(f"  Swift - base: U refused {du:+.3f} [{duci[0]:+.3f}, {duci[1]:+.3f}]  H correct {dh:+.3f} [{dhci[0]:+.3f}, {dhci[1]:+.3f}]")
def cal(arm):
    rows = []
    for f in sorted(glob.glob(str(H / "swift_bonsai" / arm / "armA_rep*.jsonl"))):
        rows += [json.loads(l) for l in open(f) if l.strip()]
    return rows
C = {}
for arm in ("BONB9", "SWB9"):
    r = cal(arm); U = [x for x in r if x["arm"] == "unanswerable"]; A = [x for x in r if x["arm"] == "answerable"]
    C[arm] = {"n": len(r), "A": sum(x["status"] == "ANSWERED-CORRECT" for x in A), "Uab": sum(x["status"] == "ABSTAINED" for x in U),
              "Uwr": sum(x["status"] == "ANSWERED-WRONG" for x in U), "nostop": sum(x["status"].startswith("NO-STOP") for x in r),
              "Umed": st.median([len(x.get("reasoning") or "") for x in U] or [0]), "Amed": st.median([len(x.get("reasoning") or "") for x in A] or [0])}
    c = C[arm]; print(f"CAL {arm}: n={c['n']} answerable {c['A']}/24  unanswerable abstained {c['Uab']}/24 wrong {c['Uwr']}  NO-STOP {c['nostop']}  "
                      f"median reasoning U {c['Umed']:.0f} / A {c['Amed']:.0f} ch")
res = {"S1": duci[0] <= 0, "S2": dhci[0] <= 0 <= dhci[1]}
if C["BONB9"]["n"] == 48 and C["SWB9"]["n"] == 48:
    res["S3"] = C["SWB9"]["Umed"] <= 0.8 * C["BONB9"]["Umed"]; res["S4"] = C["SWB9"]["Uab"] <= C["BONB9"]["Uab"]
for k, v in res.items(): print(k, "HOLDS" if v else "does not hold")
