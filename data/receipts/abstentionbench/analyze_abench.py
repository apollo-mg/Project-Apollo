#!/usr/bin/env python3
"""PREREG_ABSTENTIONBENCH analysis. Per dataset: precision / recall / F1 with abstention as the positive class
(sklearn semantics, as analysis/tables.py), judge verdict None dropped and counted. Gate: our Llama 3.1 8B Instruct
(exact judge) vs Meta's published rows on the 18 datasets reported unsplit. Judge leakage: exact vs blind verdicts.
Usage: analyze_abench.py --checkout DIR --arm ARM [--out RESULT_ARM.json]"""
import argparse, csv, json, statistics as st
from pathlib import Path
HERE = Path(__file__).resolve().parent
NAME = {"ALCUNADataset": "ALCUNA", "BigBenchDisambiguateDataset": "BB/Disambiguate", "BigBenchKnownUnknownsDataset": "BB/Known unknowns",
        "BBQDataset": "BBQ", "FalseQADataset": "FalseQA", "GPQA": "GPQA-Diamond", "GSM8K": "GSM8K", "MMLUHistory": "MMLU History",
        "MMLUMath": "MMLU Math", "MediQDataset": "MediQ", "MoralChoiceDataset": "MoralChoice", "MusiqueDataset": "Musique",
        "QAQADataset": "QAQA", "QASPERDataset": "QASPER", "Squad2Dataset": "SQuAD 2.0", "SituatedQAGeoDataset": "SituatedQA/Geo",
        "UMWP": "UMWP", "WorldSenseDataset": "WorldSense"}
def prf(rows):
    tp = sum(1 for y, p in rows if y and p); fp = sum(1 for y, p in rows if not y and p); fn = sum(1 for y, p in rows if y and not p)
    P = tp / (tp + fp) if tp + fp else 0.0; R = tp / (tp + fn) if tp + fn else 0.0
    return P, R, (2 * P * R / (P + R) if P + R else 0.0)
def load(path):
    return {(r["dataset"], r["index"]): r for r in map(json.loads, open(path)) if "error" not in r}
def spearman(x, y):
    rk = lambda v: {i: r for r, i in enumerate(sorted(range(len(v)), key=lambda k: v[k]))}
    rx, ry = rk(x), rk(y); n = len(x)
    return 1 - 6 * sum((rx[i] - ry[i]) ** 2 for i in range(n)) / (n * (n * n - 1))
ap = argparse.ArgumentParser(); ap.add_argument("--checkout", required=True); ap.add_argument("--arm", required=True)
ap.add_argument("--out"); ap.add_argument("--published-model", default="Llama 3.1 8B Instruct")
a = ap.parse_args()
out = {"arm": a.arm}
for var in ("exact", "blind"):
    p = HERE / "raw" / f"{a.arm}.judge_{var}.jsonl"
    if not p.exists(): continue
    J = load(p); none = sum(1 for r in J.values() if r["verdict"] is None)
    by = {}
    for (ds, i), r in J.items():
        if r["verdict"] is None: continue
        by.setdefault(ds, []).append((bool(r["should_abstain"]), bool(r["verdict"])))
    out[var] = {"none_verdicts": none, "per_dataset": {ds: dict(zip(("precision", "recall", "f1"), [round(x, 3) for x in prf(v)]), n=len(v)) for ds, v in sorted(by.items())}}
    allrows = [x for v in by.values() for x in v]; out[var]["pooled"] = dict(zip(("precision", "recall", "f1"), [round(x, 3) for x in prf(allrows)]))
    out[var]["mean_f1_over_datasets"] = round(st.mean(d["f1"] for d in out[var]["per_dataset"].values()), 3)
pub = {r["dataset_name_formatted"]: float(r["f1_score"]) for r in csv.DictReader(open(Path(a.checkout) / "analysis/abstention_performance.csv"))
       if r["model_name_formatted"] == a.published_model}
if "exact" in out and pub:
    pairs = [(NAME[ds], out["exact"]["per_dataset"][ds]["f1"], pub[NAME[ds]]) for ds in NAME if ds in out["exact"]["per_dataset"] and NAME[ds] in pub]
    mad = st.mean(abs(o - p) for _, o, p in pairs); rho = spearman([o for _, o, _ in pairs], [p for _, _, p in pairs])
    out["gate"] = {"published_model": a.published_model, "n_datasets": len(pairs), "mean_abs_f1_diff": round(mad, 3), "spearman": round(rho, 3),
                   "passes": mad <= 0.10 and rho >= 0.6, "rows": [{"dataset": n, "ours": o, "published": p} for n, o, p in pairs]}
if "exact" in out and "blind" in out:
    E = load(HERE / "raw" / f"{a.arm}.judge_exact.jsonl"); B = load(HERE / "raw" / f"{a.arm}.judge_blind.jsonl")
    keys = [k for k in E if k in B and E[k]["verdict"] is not None and B[k]["verdict"] is not None]
    flips = [k for k in keys if E[k]["verdict"] != B[k]["verdict"]]
    toward = sum(1 for k in flips if E[k]["verdict"] == bool(E[k]["should_abstain"]))
    out["leakage"] = {"n": len(keys), "flips": len(flips), "flip_rate": round(len(flips) / max(1, len(keys)), 3),
                      "flips_where_exact_agrees_with_label": toward,
                      "mean_f1_exact_minus_blind": round(out["exact"]["mean_f1_over_datasets"] - out["blind"]["mean_f1_over_datasets"], 3)}
json.dump(out, open(a.out or HERE / f"RESULT_{a.arm}.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ("exact", "blind")}, indent=1)[:3000])
for var in ("exact", "blind"):
    if var in out: print(var, "pooled", out[var]["pooled"], "mean F1", out[var]["mean_f1_over_datasets"], "None", out[var]["none_verdicts"])
