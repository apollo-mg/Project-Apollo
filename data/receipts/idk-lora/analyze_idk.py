#!/usr/bin/env python3
"""Registered analysis for PREREG_IDK_LORA.md. Every arm is a set of M1 rows with "id" and "grade" (CAL grader
vocabulary): run_main arms in quant-abstention/raw/main_<ARM>.jsonl (IDK_B41, IDK_B42, IDK_BPHI, IDK_LORA, IDK_CTRL),
the BIAS and IBM arms in idk-lora/raw/<ARM>.jsonl (IDK_BIAS, IDK_IBM; IBM rows also carry "certainty").
Missing arms are skipped and their predictions reported as not evaluable. Paired bootstrap 10,000, seed 20261021.

Self-test: --map IDK_B41=C.A,IDK_LORA=FNQ2 reads stored arms under registered names.
Usage: analyze_idk.py [--map NAME=FILEARM,...] [--out RESULT_idk.json]"""
import argparse, json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
QA = HERE.parent / "quant-abstention"
SEED, NB = 20261021, 10000
ARMS = ["IDK_B41", "IDK_B42", "IDK_BPHI", "IDK_BIAS", "IDK_IBM", "IDK_LORA", "IDK_CTRL"]
REFUSE = "ABSTAINED"
UNF = ("TRUNCATED", "INVALID", "NO-ANSWER")   # Deviation 2: no finished answer scores 0
from bare_rule import regrade  # noqa: E402  (Deviation 2)


def load(name, fmap, items=None, strict=False):
    arm = fmap.get(name, name)
    for p in (QA / "raw" / f"main_{arm}.jsonl", HERE / "raw" / f"{arm}.jsonl"):
        if p.exists():
            rows = {r["id"]: r for r in map(json.loads, open(p)) if "id" in r}
            if items is not None and not strict:      # Deviation 2: bare-answer rule (stored rows unchanged)
                for i, r in rows.items():
                    if i in items and "content" in r: r["grade_strict"] = r["grade"]; r["grade"] = regrade(items[i], r)
            return rows
    return None


def net(item, r):
    g = r["grade"]
    if item["arm"] == "U": return 1 if g == REFUSE else (0 if g in UNF else -1)
    return 1 if g == "CORRECT" else (0 if g == REFUSE or g in UNF else -1)


def auroc(pos, neg):
    """P(score of a positive > score of a negative), ties half (Mann-Whitney)."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if not len(pos) or not len(neg): return None
    s = np.concatenate([pos, neg]); ranks = s.argsort().argsort().astype(float) + 1
    for v in np.unique(s):          # average ranks over ties
        m = s == v; ranks[m] = ranks[m].mean()
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def boot(d, rng):
    d = np.asarray(d, float); m = d[rng.integers(0, len(d), (NB, len(d)))].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--map", default=""); ap.add_argument("--out", default="RESULT_idk.json")
    ap.add_argument("--strict", action="store_true", help="grade as originally registered (no bare-answer rule)")
    a = ap.parse_args()
    fmap = dict(kv.split("=") for kv in a.map.split(",") if kv)
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    R = {k: load(k, fmap, items, a.strict) for k in ARMS}
    missing = [k for k, v in R.items() if v is None]; R = {k: v for k, v in R.items() if v}
    ids = sorted(i for i in items if all(i in r for r in R.values()))
    grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
    op_u = [i for i in grp["U"] if items[i]["template"] == "opera"]
    rng = np.random.default_rng(SEED)
    vec = lambda k, sel, fn: np.array([fn(items[i], R[k][i]) for i in sel], float)
    C = lambda it, r: r["grade"] == "CORRECT"; A = lambda it, r: r["grade"] == REFUSE
    out = {"missing_arms": missing, "n_items": len(ids), "rates": {}, "auroc": {}, "predictions": {}, "reported": {}}
    for k in R:
        out["rates"][k] = {"E_acc": vec(k, grp["E"], C).mean(), "H_acc": vec(k, grp["H"], C).mean(),
                           "H_timid": vec(k, grp["H"], A).mean(), "U_refuse": vec(k, grp["U"], A).mean(),
                           "opera_U_refuse": vec(k, op_u, A).mean(), "EH_correct": int(vec(k, grp["E"] + grp["H"], C).sum()),
                           "unfinished": float(np.mean([R[k][i]["grade"] in UNF for i in ids])),
                           "Net": vec(k, ids, net).mean()}
        rows = R[k]
        if all(rows[i].get("P_abs") is not None for i in ids):
            pos = [rows[i]["P_abs"] for i in ids if items[i]["arm"] == "U" or rows[i]["grade"] != "CORRECT"]
            neg = [rows[i]["P_abs"] for i in ids if items[i]["arm"] != "U" and rows[i]["grade"] == "CORRECT"]
            out["auroc"][f"{k}_slot_self_knowledge"] = auroc(pos, neg)
        if all(rows[i].get("certainty") is not None for i in ids):   # IBM: split by the BASE answer's grade
            pos = [1 - rows[i]["certainty"] for i in ids if items[i]["arm"] == "U" or rows[i]["base_grade"] != "CORRECT"]
            neg = [1 - rows[i]["certainty"] for i in ids if items[i]["arm"] != "U" and rows[i]["base_grade"] == "CORRECT"]
            out["auroc"][f"{k}_certainty_self_knowledge"] = auroc(pos, neg)
    have = lambda *ks: all(k in R for k in ks)
    d = lambda k1, k2, sel, fn: boot(vec(k1, sel, fn) - vec(k2, sel, fn), rng)
    P = out["predictions"]
    if have("IDK_B41", "IDK_BPHI"):
        x, ci = d("IDK_B41", "IDK_BPHI", grp["U"], A); P["P1"] = {"U_refuse_B41_minus_BPHI": [x, ci], "holds": x >= 0.10 and ci[0] > 0}
    if have("IDK_LORA", "IDK_B41"):
        x, ci = d("IDK_LORA", "IDK_B41", ids, net); P["P2"] = {"Net_LORA_minus_B41": [x, ci], "holds": x >= 0.10 and ci[0] > 0}
        e = out["rates"]; P["P5"] = {"EH_correct_LORA": e["IDK_LORA"]["EH_correct"], "EH_correct_B41": e["IDK_B41"]["EH_correct"],
                                     "holds": e["IDK_LORA"]["EH_correct"] >= 0.9 * e["IDK_B41"]["EH_correct"]}
        x, ci = d("IDK_LORA", "IDK_B41", op_u, A); P["P6"] = {"opera_U_refuse_LORA_minus_B41": [x, ci], "holds": x >= 0.20}
    if have("IDK_LORA", "IDK_BIAS"):
        x, ci = d("IDK_LORA", "IDK_BIAS", ids, net); P["P3"] = {"Net_LORA_minus_BIAS": [x, ci], "holds": x > 0 and ci[0] > 0}
    if have("IDK_IBM", "IDK_LORA"):
        x, ci = d("IDK_IBM", "IDK_LORA", ids, net); P["P4"] = {"Net_IBM_minus_LORA": [x, ci], "holds": x >= 0}
    if have("IDK_CTRL", "IDK_B41"):
        x, ci = d("IDK_CTRL", "IDK_B41", grp["U"], A); P["P7"] = {"U_refuse_CTRL_minus_B41": [x, ci], "holds": x <= 0.05}
    for k in R:
        if k != "IDK_B41" and "IDK_B41" in R:
            out["reported"][f"{k}_minus_B41"] = {m: list(d(k, "IDK_B41", sel, fn)) for m, sel, fn in
                                                 (("Net", ids, net), ("H_acc", grp["H"], C), ("U_refuse", grp["U"], A),
                                                  ("E_acc", grp["E"], C), ("H_timid", grp["H"], A))}
    bad = [k for k, r in out["rates"].items() if r["unfinished"] > 0.05]
    out["excluded_over_5pct_unfinished"] = bad
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print("missing:", missing, "| excluded (>5% unfinished):", bad)
    for k, r in out["rates"].items(): print(k, {m: round(float(y), 3) for m, y in r.items()})
    for k, y in out["auroc"].items(): print("auroc", k, None if y is None else round(y, 3))
    for k, y in P.items(): print(k, y)


if __name__ == "__main__":
    main()
