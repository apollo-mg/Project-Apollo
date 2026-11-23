#!/usr/bin/env python3
"""Registered analysis for PREREG_FROZEN_LAYERS.md. Arms: quant-abstention/raw/main_FZ_<ARM>.jsonl, graded with the
bare-answer rule of PREREG_IDK_LORA Deviation 2 (idk-lora/bare_rule.py), exactly as idk-lora/analyze_idk.py.
Primary: r(arm) = share of the 100 invented items refused; D(arm) = r(BASE) - r(arm); S(arm) = D(arm) / D(ALL).
Paired bootstrap over the invented items, 10,000 resamples, seed 20261123.
Usage: analyze_frozen.py [--out RESULT_frozen.json]"""
import argparse, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent / "idk-lora")); from bare_rule import regrade  # noqa: E402
SEED, NB = 20261123, 10000
ARMS = ["FZ_BASE", "FZ_ALL", "FZ_FRZ10", "FZ_FRZ20", "FZ_LAST20"]
LAYERS = {"FZ_BASE": "none", "FZ_ALL": "0-39", "FZ_FRZ10": "0-29", "FZ_FRZ20": "0-19", "FZ_LAST20": "20-39"}
UNF = ("TRUNCATED", "INVALID", "NO-ANSWER")


def load(arm, items):
    p = QA / "raw" / f"main_{arm}.jsonl"
    if not p.exists(): return None
    rows = {r["id"]: r for r in map(json.loads, open(p)) if "id" in r}
    for i, r in rows.items():
        if i in items and "content" in r: r["grade"] = regrade(items[i], r)
    return rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "RESULT_frozen.json"))
    ap.add_argument("--suffix", default="", help="Amendment 1 replicate arms, e.g. _S1 (FZ_BASE stays shared)"); a = ap.parse_args()
    global ARMS, LAYERS
    if a.suffix:
        ARMS = ["FZ_BASE"] + [x + a.suffix for x in ARMS[1:]]
        LAYERS = {k + (a.suffix if k != "FZ_BASE" else ""): v for k, v in LAYERS.items()}
    N = lambda x: x + a.suffix
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    U = sorted(i for i, x in items.items() if x["arm"] == "U")
    R = {arm: load(arm, items) for arm in ARMS}
    have = [arm for arm in ARMS if R[arm] is not None and all(i in R[arm] for i in items)]
    out = {"arms": {}, "tests": {}}
    print(f"# frozen layers: arms complete {have}\n")
    print(f"{'arm':10s} {'layers':6s} {'inv. refused':>12s} {'E right/wrong':>14s} {'H right/wrong/refused':>22s} {'unfin':>5s} {'final loss':>10s} {'train s':>7s}")
    ref = {}
    for arm in have:
        rows = R[arm]
        ref[arm] = np.array([rows[i]["grade"] == "ABSTAINED" for i in U], float)
        cnt = lambda arm_, g: sum(1 for i, x in items.items() if x["arm"] == arm_ and rows[i]["grade"] == g)
        wrong = lambda arm_: sum(1 for i, x in items.items() if x["arm"] == arm_
                                 and rows[i]["grade"] not in ("CORRECT", "ABSTAINED") and rows[i]["grade"] not in UNF)
        unf = sum(1 for i in items if rows[i]["grade"] in UNF)
        tl = HERE / "raw" / f"train_log_{arm}.json"
        loss = secs = None
        if tl.exists():
            t = json.load(open(tl)); loss = float(np.mean([s["loss"] for s in t["log"][-5:]])); secs = t["seconds"]
        out["arms"][arm] = {"layers": LAYERS[arm], "invented_refused": int(ref[arm].sum()),
                            "E_correct": cnt("E", "CORRECT"), "E_wrong": wrong("E"),
                            "H_correct": cnt("H", "CORRECT"), "H_wrong": wrong("H"), "H_refused": cnt("H", "ABSTAINED"),
                            "unfinished": unf, "final_loss_last5": loss, "train_seconds": secs}
        o = out["arms"][arm]
        print(f"{arm:10s} {LAYERS[arm]:6s} {o['invented_refused']:>8d}/100 {o['E_correct']:>8d}/{o['E_wrong']:<5d} "
              f"{o['H_correct']:>10d}/{o['H_wrong']}/{o['H_refused']:<6d} {unf:>5d} "
              f"{(f'{loss:.4f}' if loss is not None else '-'):>10s} {(secs if secs is not None else '-'):>7}")
    if "FZ_BASE" not in ref or N("FZ_ALL") not in ref:
        print("\nbase or reference arm missing: no tests"); json.dump(out, open(a.out, "w"), indent=1); return
    rng = np.random.default_rng(SEED); idx = rng.integers(0, len(U), (NB, len(U)))
    rb = ref["FZ_BASE"]; D = lambda arm: rb - ref[arm]
    ci = lambda v: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)))
    dall_bs = D(N("FZ_ALL"))[idx].mean(1)
    print("\n## Tests (drop D = base minus arm, invented items; S = D(arm) / D(FZ_ALL))\n")
    r_all = ref[N("FZ_ALL")].mean()
    m_ok = r_all <= 0.40
    out["tests"]["M"] = {"r_ALL": r_all, "holds": bool(m_ok)}
    print(f"- M  manipulation check: r(FZ_ALL) = {r_all:.2f} (base {rb.mean():.2f}) -> {'holds' if m_ok else 'FAILS: replication failed, H1-H2 not evaluated'}")
    for arm in (N("FZ_FRZ10"), N("FZ_FRZ20"), N("FZ_LAST20")):
        if arm not in ref: continue
        d = D(arm); d_bs = d[idx].mean(1)
        with np.errstate(divide="ignore", invalid="ignore"):
            s_bs = np.where(dall_bs > 0, d_bs / dall_bs, np.nan)
        s = d.mean() / D(N("FZ_ALL")).mean() if D(N("FZ_ALL")).mean() > 0 else float("nan")
        s_ci = (float(np.nanpercentile(s_bs, 2.5)), float(np.nanpercentile(s_bs, 97.5)))
        out["tests"][arm] = {"D": float(d.mean()), "D_ci95": ci(d_bs), "S": float(s), "S_ci95": s_ci}
        line = (f"- {arm}: D = {d.mean():+.2f} [{ci(d_bs)[0]:+.2f}, {ci(d_bs)[1]:+.2f}], "
                f"S = {s:.2f} [{s_ci[0]:.2f}, {s_ci[1]:.2f}]")
        if m_ok and arm == N("FZ_FRZ10"):
            h1 = s >= 0.5 and ci(d_bs)[0] > 0
            out["tests"]["H1"] = bool(h1)
            line += f"  H1 (last 10 frozen does NOT protect) -> {'holds' if h1 else 'FAILS: freezing the last 10 protects most of it'}"
        if m_ok and arm == N("FZ_FRZ20"):
            h2 = s >= 0.5
            out["tests"]["H2"] = bool(h2)
            line += f"  H2 (last 20 frozen does NOT protect) -> {'holds' if h2 else 'FAILS: freezing the last 20 protects most of it'}"
        print(line)
    if N("FZ_FRZ20") in ref and N("FZ_LAST20") in ref:
        h3 = D(N("FZ_FRZ20")) - D(N("FZ_LAST20")); h3_bs = h3[idx].mean(1)
        out["tests"]["H3"] = {"D_FRZ20_minus_D_LAST20": float(h3.mean()), "ci95": ci(h3_bs)}
        print(f"- H3 first half vs last half (D(FZ_FRZ20) - D(FZ_LAST20)): {h3.mean():+.2f} [{ci(h3_bs)[0]:+.2f}, {ci(h3_bs)[1]:+.2f}] (no direction predicted)")
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
