#!/usr/bin/env python3
"""Score C4/C5 against PREREG_C4_C5.md. Committed gold-rate = gold / (gold + wrong)."""
import json, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade

def load(p):
    d = {}
    for l in open(p):
        l = l.strip()
        if not l: continue
        r = json.loads(l)
        c = r["id"].rsplit("__", 1)[1]
        v, _ = grade(r["gold"], r.get("response", ""), 25, r.get("finish_reason"))
        d.setdefault(c, []).append(v)
    return d

A = {"base": load(sys.argv[1]), "pruned": load(sys.argv[2])}
LBL = {"C4a": "gold 2nd, AUTH on gold", "C4b": "gold 1st, AUTH on confab",
       "C5a": "foreign wrong, gold 1st", "C5b": "foreign wrong, gold 2nd"}
hdr = f"{'arm':<8}{'cell':<6}{'layout':<26}{'gold':>6}{'wrong':>7}{'refus':>7}{'committed gold':>16}"
print(hdr); print("-" * len(hdr))
R = {}
for lab in ("base", "pruned"):
    for c in ("C4a", "C4b", "C5a", "C5b"):
        v = A[lab].get(c, [])
        if not v: continue
        g = v.count("CORRECT"); w = v.count("WRONG"); rf = len(v) - g - w
        R[(lab, c)] = g / (g + w) if g + w else float("nan")
        print(f"{lab:<8}{c:<6}{LBL[c]:<26}{g:>6}{w:>7}{rf:>7}{R[(lab,c)]:>15.1%}")
    print("-" * len(hdr))

print("\n=== PREDICTION SCORING (PREREG_C4_C5.md §8) ===")
bs = abs(R[("base","C5a")] - R[("base","C5b")])
gate = bs <= 0.20
print(f"  P-C5G GATE base C5 order sensitivity <=20pp : {bs*100:.1f}pp -> {'HELD' if gate else 'FAILED'}")
print(f"  P-C4a pruned C4a >=70%   (C3 gold-2nd was 33.9%) : {R[('pruned','C4a')]:.1%} -> "
      f"{'HELD' if R[('pruned','C4a')]>=0.70 else 'FALSIFIED'}")
d4b = R[("base","C4b")] - R[("pruned","C4b")]
print(f"  P-C4b pruned C4b >=15pp below base : base {R[('base','C4b')]:.1%} vs pruned "
      f"{R[('pruned','C4b')]:.1%}, gap {d4b*100:+.1f}pp -> {'HELD' if d4b>=0.15 else 'FALSIFIED'}")
ps = abs(R[("pruned","C5a")] - R[("pruned","C5b")])
if gate:
    print(f"  P-C5  pruned C5 order sensitivity >=30pp : {ps*100:.1f}pp -> "
          f"{'HELD' if ps>=0.30 else 'FALSIFIED'}")
else:
    print("  P-C5  NOT SCORED — gate P-C5G failed")
print(f"\n  C4 tag-following check: pruned C4a {R[('pruned','C4a')]:.1%} / C4b {R[('pruned','C4b')]:.1%}")
print("    high C4a + LOW C4b = swapped position for tag (manipulable, not a fix)")
print("    high C4a + high C4b = provenance used as evidence (a real fix)")
print(f"  order sensitivity, C5: base {bs*100:.1f}pp, pruned {ps*100:.1f}pp   (C3 was 6.6 / 59.1)")
