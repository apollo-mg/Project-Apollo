#!/usr/bin/env python3
"""Registered analysis for PREREG_JLENS_IDK.md. Bootstrap 10,000, seed 20261023.
u_rank = best rank of any U-set token over layers 12-29 (J-lens; `lrank` = logit-lens control).
Usage: analyze_jlens.py [--raw DIR] [--e2 DIR] [--out FILE]"""
import argparse, json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB, BAND = 20261023, 10000, range(12, 30)


def urank(row, key):
    return min(min(row[key][str(L)]) for L in BAND if str(L) in row[key])


def boot_median_diff(a, b, rng):          # unpaired: median(a) - median(b)
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = [np.median(a[rng.integers(0, len(a), len(a))]) - np.median(b[rng.integers(0, len(b), len(b))]) for _ in range(NB)]
    return float(np.median(a) - np.median(b)), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def boot_median(d, rng):                  # paired differences
    d = np.asarray(d, float); m = [np.median(d[rng.integers(0, len(d), len(d))]) for _ in range(NB)]
    return float(np.median(d)), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def auroc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if not len(pos) or not len(neg): return None
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--raw", default=str(HERE / "raw"))
    ap.add_argument("--e2", default=str(HERE.parent / "idk-lora" / "raw")); ap.add_argument("--out", default="RESULT_jlens.json")
    a = ap.parse_args()
    L = {arm: {r["id"]: r for r in map(json.loads, open(Path(a.raw) / f"lens_{arm}.jsonl"))} for arm in ("BASE", "LORA", "LORA2")}
    E = {arm: {r["id"]: r for r in map(json.loads, open(Path(a.e2) / f"E2_{arm}.jsonl"))} for arm in ("BASE", "LORA", "LORA2")}
    ids = sorted(L["BASE"]); B = L["BASE"]
    inv = lambda t: [i for i in ids if B[i]["arm"] == "U" and B[i]["template"] in t]
    nov, capuni = inv(("novel",)), inv(("capital", "university"))
    out = {"sanity": {}, "hypotheses": {}, "control_logit_lens": {}, "reported": {}}
    for arm in L:
        out["sanity"][arm] = float(np.mean([L[arm][i]["lens_top1_last"] == L[arm][i]["model_top1"] for i in ids]))
    gate = out["sanity"]["BASE"] >= 0.80; out["gate_passed"] = gate
    for key, sink in (("jrank", out["hypotheses"]), ("lrank", out["control_logit_lens"])):
        rng = np.random.default_rng(SEED)
        u = {arm: {i: urank(L[arm][i], key) for i in ids} for arm in L}
        x, ci = boot_median_diff([u["BASE"][i] for i in nov], [u["BASE"][i] for i in capuni], rng)
        sink["J1"] = {"median_urank_novel_minus_capuni_BASE": [x, ci], "holds": gate and x > 0 and ci[0] > 0}
        refused = [i for i in inv(("capital", "novel", "opera", "university")) if E["LORA2"][i]["strict"] == "ABSTAINED"]
        answered = [i for i in inv(("capital", "novel", "opera", "university")) if E["LORA2"][i]["strict"] != "ABSTAINED"]
        au = auroc([-u["LORA2"][i] for i in refused], [-u["LORA2"][i] for i in answered])
        sink["J2"] = {"auroc_refused_vs_answered_LORA2": au, "n_refused": len(refused), "n_answered": len(answered),
                      "holds": gate and au is not None and au >= 0.70}
        x, ci = boot_median([u["LORA2"][i] - u["BASE"][i] for i in capuni], rng)
        sink["J3"] = {"paired_median_LORA2_minus_BASE_capuni": [x, ci], "holds": gate and x < 0 and ci[1] < 0}
        dn = np.array([u["LORA2"][i] - u["BASE"][i] for i in nov]); dc = np.array([u["LORA2"][i] - u["BASE"][i] for i in capuni])
        m = [np.median(dn[rng.integers(0, len(dn), len(dn))]) - np.median(dc[rng.integers(0, len(dc), len(dc))]) for _ in range(NB)]
        x = float(np.median(dn) - np.median(dc)); ci = (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))
        sink["J4"] = {"drop_novel_minus_drop_capuni": [x, ci], "holds": gate and x > 0 and ci[0] > 0}
        if key == "jrank":
            conf = [i for i in inv(("capital", "novel", "opera", "university")) if E["BASE"][i]["strict"] != "ABSTAINED"]
            out["reported"]["BASE_confabulated_invented_with_urank_le_50"] = [sum(u["BASE"][i] <= 50 for i in conf), len(conf)]
            out["reported"]["median_urank"] = {arm: {t: float(np.median([u[arm][i] for i in inv((t,))]))
                                                     for t in ("capital", "novel", "opera", "university")} for arm in L}
            real = [i for i in ids if B[i]["arm"] != "U"]
            ok = [i for i in real if E["BASE"][i]["strict"] == "CORRECT"]; bad = [i for i in real if E["BASE"][i]["strict"] != "CORRECT"]
            out["reported"]["BASE_real_auroc_wrong_vs_correct"] = auroc([-u["BASE"][i] for i in bad], [-u["BASE"][i] for i in ok])
            out["reported"]["per_layer_median_jrank"] = {arm: {grp: [float(np.median([min(L[arm][i]["jrank"][str(l)]) for i in sel]))
                                                                    for l in range(40) if str(l) in L[arm][ids[0]]["jrank"]]
                                                               for grp, sel in (("invented_novel", nov), ("invented_capuni", capuni))}
                                                          for arm in L}
    json.dump(out, open(HERE / a.out, "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("sanity", "gate_passed", "hypotheses", "control_logit_lens")}, indent=1))
    print("reported:", {k: v for k, v in out["reported"].items() if k != "per_layer_median_jrank"})


if __name__ == "__main__":
    main()
