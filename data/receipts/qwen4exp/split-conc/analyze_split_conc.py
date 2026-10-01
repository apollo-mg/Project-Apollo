#!/usr/bin/env python3
"""Registered analysis for PREREG_SPLIT_CONC.md. Pass-2 rows only. Tensor cells count only if their ref (first 64
tokens of P[0]) equals L0's and G0 passed (a cell without pass-2 rows is invalid). usage: analyze_split_conc.py [RAWDIR]"""
import json, sys
from pathlib import Path
H = Path(__file__).resolve().parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else H / "raw"
rows = [json.loads(l) for l in open(RAW / "rows.jsonl") if l.strip()] if (RAW / "rows.jsonl").exists() else []
refs = {}
if (RAW / "refs.jsonl").exists():
    for l in open(RAW / "refs.jsonl"):
        try:
            d = json.loads(l); refs[d["cell"]] = d["ref"]
        except Exception:
            pass
R = {(r["cell"], r["n"]): r for r in rows if r["pass"] == 2}
valid = {c: True for c in ("L0", "L3")}
for c in ("T0", "T3"):
    valid[c] = refs.get(c) is not None and refs.get(c) == refs.get("L0")
for c in ("L0", "L3", "T0", "T3"):
    line = []
    for n in (1, 2, 4):
        r = R.get((c, n))
        if r:
            acc = f" acc {r['draft_acc'] / r['draft_n']:.2f}" if r["draft_n"] else ""
            line.append(f"n={n}: {r['agg_tps']:6.2f} total, per-stream {r['per_stream']} ok {r['ok']}/{n}{acc}" + (f" ERR {r['errs']}" if r["fail"] else ""))
    print(f"{c} ({'valid' if valid[c] else 'INVALID: ref differs from L0 or missing'}):\n   " + "\n   ".join(line or ["no rows"]))
res = {}
a = lambda c, n: R[(c, n)]["agg_tps"] if (c, n) in R and R[(c, n)]["ok"] else None
if a("L0", 1) and a("L0", 4):
    res["S1"] = a("L0", 4) >= 1.6 * a("L0", 1); print(f"S1: L0 4/1 = {a('L0', 4) / a('L0', 1):.2f}")
if ("L3", 4) in R and ("L3", 2) in R:
    r4 = R[("L3", 4)]; res["S2"] = r4["fail"] > 0 or r4["agg_tps"] < R[("L3", 2)]["agg_tps"]
    print(f"S2: L3 n=4 fail {r4['fail']}, total {r4['agg_tps']} vs n=2 {R[('L3', 2)]['agg_tps']}")
if valid["T0"] and a("T0", 1) and a("L0", 1):
    res["S3"] = a("T0", 1) < a("L0", 1); print(f"S3: T0 n=1 {a('T0', 1)} vs L0 n=1 {a('L0', 1)}")
if valid["T0"] and a("T0", 1) and a("T0", 4) and a("L0", 1) and a("L0", 4):
    res["S4"] = a("T0", 4) / a("T0", 1) > a("L0", 4) / a("L0", 1); print(f"S4: T0 4/1 {a('T0', 4) / a('T0', 1):.2f} vs L0 {a('L0', 4) / a('L0', 1):.2f}")
for k in ("S1", "S2", "S3", "S4"):
    print(k, ("HOLDS" if res[k] else "does not hold") if k in res else "pending / invalid")
if len(sys.argv) == 1:
    json.dump({"verdicts": res, "valid": valid, "pass2": {f"{c}|{n}": r for (c, n), r in R.items()}}, open(H / "RESULT_split_conc.json", "w"), indent=1)
