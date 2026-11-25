#!/usr/bin/env python3
"""Registered analysis for PREREG_STACK_DRIFT.md. M1 arms in quant-abstention/raw/main_<ARM>.jsonl, graded with the
bare-answer rule (idk-lora/bare_rule.py); KLD logs raw/kld_<stack>.log (desk: raw/desk/kld_desk.log).
Paired bootstrap over items, 10,000 resamples, seed 20261124. Usage: analyze_drift.py [--out RESULT_drift.json]"""
import argparse, json, re, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent / "idk-lora")); from bare_rule import regrade  # noqa: E402
SEED, NB = 20261124, 10000


def load(arm, items):
    p = QA / "raw" / f"main_{arm}.jsonl"
    if not p.exists(): return None
    rows = {r["id"]: r for r in map(json.loads, open(p)) if "id" in r}
    if not all(i in rows for i in items): return None
    for i, r in rows.items():
        if i in items and "content" in r: r["grade"] = regrade(items[i], r)
    return rows


def kld(path):
    if not path.exists(): return None
    t = open(path, errors="replace").read()
    def num(pat):
        m = re.search(pat, t); return float(m.group(1)) if m else None
    return {"mean_kld": num(r"Mean\s+KLD:\s+([0-9.eE+-]+)"), "kld_99": num(r"99\.0%\s+KLD:\s+([0-9.eE+-]+)"),
            "same_top_p_pct": num(r"Same top p:\s+([0-9.]+)"), "ppl_q": num(r"Mean\s+PPL\(Q\)\s*:\s*([0-9.]+)"),
            "ppl_base": num(r"Mean\s+PPL\(base\)\s*:\s*([0-9.]+)")}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "RESULT_drift.json")); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    U = sorted(i for i, x in items.items() if x["arm"] == "U"); Hh = sorted(i for i, x in items.items() if x["arm"] == "H")
    E = sorted(i for i, x in items.items() if x["arm"] == "E")
    arms = ["DR_DESK_1", "DR_DESK_2", "DR_N194_1", "DR_N194_2", "DR_N73_1", "DR_N73_2", "DR27_N194", "DR27_N73"]
    R = {x: load(x, items) for x in arms}
    out = {"totals": {}, "pairs": {}, "kld": {}, "tests": {}}
    print("## Totals (bare-answer rule)\n")
    for x, r in R.items():
        if r is None: print(f"{x:10s} missing or incomplete"); continue
        t = {"invented_declined": sum(r[i]["grade"] == "ABSTAINED" for i in U), "hard_right": sum(r[i]["grade"] == "CORRECT" for i in Hh),
             "easy_right": sum(r[i]["grade"] == "CORRECT" for i in E)}
        out["totals"][x] = t; print(f"{x:10s} invented declined {t['invented_declined']:3d}/100  hard right {t['hard_right']:3d}/100  easy right {t['easy_right']:2d}/40")
    def same(x, y):
        if R.get(x) is None or R.get(y) is None: return None
        c = sum(R[x][i].get("content") == R[y][i].get("content") for i in items)
        g = sum(R[x][i]["grade"] == R[y][i]["grade"] for i in items)
        out["pairs"][f"{x} vs {y}"] = {"answers_identical": c, "grades_identical": g}; return c, g
    print("\n## Pairs (answers identical / grades identical, of 240)\n")
    pairs = [("DR_DESK_1", "DR_DESK_2"), ("DR_N194_1", "DR_N194_2"), ("DR_N73_1", "DR_N73_2"),
             ("DR_N194_1", "DR_N73_1"), ("DR_N194_2", "DR_N73_2"), ("DR_N194_1", "DR_N73_2"),
             ("DR_DESK_1", "DR_N194_1"), ("DR_DESK_1", "DR_N73_2"), ("DR27_N194", "DR27_N73")]
    for x, y in pairs:
        s = same(x, y); print(f"{x:10s} vs {y:10s}: " + ("n/a" if s is None else f"{s[0]:3d} / {s[1]:3d}"))
    rng = np.random.default_rng(SEED)
    def paired(x, y, ids, f):
        d = np.array([f(R[x][i]) - f(R[y][i]) for i in ids], float)
        bs = d[rng.integers(0, len(d), (NB, len(d)))].mean(1)
        return float(d.mean()), (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
    print("\n## Tests\n")
    d1 = [out["pairs"].get(f"{x} vs {y}") for x, y in pairs[:3]]
    if all(d1):
        h = all(p["answers_identical"] == 240 for p in d1); out["tests"]["D1"] = h
        print(f"- D1 each machine agrees with itself: {[p['answers_identical'] for p in d1]} -> {'holds' if h else 'FAILS'}")
    p2 = out["pairs"].get("DR_N194_1 vs DR_N73_1") or out["pairs"].get("DR_N194_1 vs DR_N73_2")
    if p2:
        out["tests"]["D2"] = p2["answers_identical"] == 240
        print(f"- D2 the two P100 machines identical: {p2['answers_identical']} of 240 -> {'holds' if p2['answers_identical'] == 240 else 'FAILS'}")
    p3 = out["pairs"].get("DR_DESK_1 vs DR_N194_1")
    if p3:
        di = paired("DR_DESK_1", "DR_N194_1", U, lambda r: float(r["grade"] == "ABSTAINED"))
        dh = paired("DR_DESK_1", "DR_N194_1", Hh, lambda r: float(r["grade"] == "CORRECT"))
        c1 = p3["answers_identical"] < 240; c2 = p3["grades_identical"] >= 225; c3 = di[1][0] <= 0 <= di[1][1] and dh[1][0] <= 0 <= dh[1][1]
        out["tests"]["D3"] = {"not_identical": c1, "grades_ge_225": c2, "intervals_include_0": c3, "invented": di, "hard": dh}
        print(f"- D3 desktop vs .194: answers identical {p3['answers_identical']} ({'not identical' if c1 else 'IDENTICAL'}), grades {p3['grades_identical']} "
              f"(>=225: {c2}); invented declined diff {di[0]:+.2f} [{di[1][0]:+.2f}, {di[1][1]:+.2f}], hard right diff {dh[0]:+.2f} "
              f"[{dh[1][0]:+.2f}, {dh[1][1]:+.2f}] (both include 0: {c3}) -> {'holds' if c1 and c2 and c3 else 'FAILS'}")
    print("\n## D4 logits against the CPU reference (10 chunks)\n")
    ok = True
    for st, p in (("desk", HERE / "raw" / "desk" / "kld_desk.log"), ("n194", HERE / "raw" / "kld_n194.log"), ("n73", HERE / "raw" / "kld_n73.log")):
        k = kld(p); out["kld"][st] = k
        if k is None or k["mean_kld"] is None: print(f"{st:5s} missing"); ok = False; continue
        good = k["mean_kld"] < 0.005 and (k["same_top_p_pct"] or 0) >= 98; ok &= good
        print(f"{st:5s} mean KLD {k['mean_kld']:.6f}  99% KLD {k['kld_99']}  same top {k['same_top_p_pct']} %  PPL {k['ppl_q']} (base {k['ppl_base']})")
    out["tests"]["D4"] = ok; print(f"- D4 -> {'holds' if ok else 'FAILS'}")
    p5 = out["pairs"].get("DR27_N194 vs DR27_N73")
    if p5:
        out["tests"]["D5"] = p5["answers_identical"] == 240
        print(f"- D5 the daily model, .194 vs .73: {p5['answers_identical']} of 240 -> {'holds' if p5['answers_identical'] == 240 else 'FAILS'}")
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
