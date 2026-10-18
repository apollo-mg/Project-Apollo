#!/usr/bin/env python3
"""Registered analysis for PREREG_IDK_LORA2.md. Paired bootstrap 10,000, seed 20261022.

E1: M1 under the M1 instruction, run_main rows (bare-answer rule) for IDK_B41, IDK_LORA, IDK_LORA2.
E2: M1 reworded in F4, raw/E2_{BASE,LORA,LORA2}.jsonl, prose-graded (strict primary, lenient reported).
Audit: raw/E2_audit.json {arm: {id: hand_grade}} (20 per arm); an arm's E2 predictions count only at >= 17/20 agreement.
Ceiling: BASE E2 invented refusal (strict) >= 0.85 -> R1 and R5 not testable.
Normal use: raw/normal_LORA2.jsonl, refusals among the 9 answerable prompts.
Usage: analyze_idk2.py [--raw DIR] [--e1map NAME=ARM,...] [--out FILE]"""
import argparse, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE)); from analyze_idk import load as load_e1   # noqa: E402
SEED, NB = 20261022, 10000


def boot(d, rng):
    d = np.asarray(d, float); m = d[rng.integers(0, len(d), (NB, len(d)))].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--raw", default=str(HERE / "raw"))
    ap.add_argument("--e1map", default=""); ap.add_argument("--out", default="RESULT_idk2.json"); a = ap.parse_args()
    raw = Path(a.raw); emap = dict(kv.split("=") for kv in a.e1map.split(",") if kv)
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    real = [i for i in items if items[i]["arm"] != "U"]; U = [i for i in items if items[i]["arm"] == "U"]
    opU = [i for i in U if items[i]["template"] == "opera"]
    rng = np.random.default_rng(SEED)
    sc = lambda g: 1 if g == "CORRECT" else (-1 if g == "WRONG" else 0)
    out = {"E1": {}, "E2": {}, "audit": {}, "predictions": {}}
    E1 = {k: load_e1(k, emap, items) for k in ("IDK_B41", "IDK_LORA", "IDK_LORA2")}
    for k, R in E1.items():
        if R: out["E1"][k] = {"real_net": int(sum(sc(R[i]["grade"]) for i in real)),
                              "U_refuse": float(np.mean([R[i]["grade"] == "ABSTAINED" for i in U]))}
    E2 = {}
    for arm in ("BASE", "LORA", "LORA2"):
        p = raw / f"E2_{arm}.jsonl"
        if p.exists(): E2[arm] = {r["id"]: r for r in map(json.loads, open(p))}
    for arm, R in E2.items():
        g = lambda i, key="strict": R[i][key]
        out["E2"][arm] = {k: v for key in ("strict", "lenient") for k, v in {
            f"E_acc_{key}": float(np.mean([g(i, key) == "CORRECT" for i in real if items[i]["arm"] == "E"])),
            f"H_acc_{key}": float(np.mean([g(i, key) == "CORRECT" for i in real if items[i]["arm"] == "H"])),
            f"H_timid_{key}": float(np.mean([g(i, key) == "ABSTAINED" for i in real if items[i]["arm"] == "H"])),
            f"U_refuse_{key}": float(np.mean([g(i, key) == "ABSTAINED" for i in U])),
            f"opera_U_refuse_{key}": float(np.mean([g(i, key) == "ABSTAINED" for i in opU])),
            f"real_net_{key}": int(sum(sc(g(i, key)) for i in real))}.items()}
    try: aud = json.load(open(raw / "E2_audit.json"))
    except FileNotFoundError: aud = {}
    ok = {}
    for arm, hand in aud.items():
        agree = sum(E2[arm][i]["strict"] == g for i, g in hand.items())
        out["audit"][arm] = {"agree": agree, "n": len(hand)}; ok[arm] = len(hand) >= 20 and agree >= 17
    out["audit_gate"] = ok
    ceiling = "BASE" in E2 and out["E2"]["BASE"]["U_refuse_strict"] >= 0.85
    out["ceiling"] = ceiling
    P = out["predictions"]
    d = lambda A, B, ids, f: boot([f(E2[A][i]) - f(E2[B][i]) for i in ids], rng)
    ref = lambda r: r["strict"] == "ABSTAINED"
    gate = lambda *arms: all(ok.get(x, False) for x in arms)
    if {"LORA2", "LORA"} <= E2.keys():
        x, ci = d("LORA2", "LORA", U, ref)
        P["R1"] = {"E2_U_refuse_LORA2_minus_LORA": [x, ci], "testable": not ceiling and gate("LORA2", "LORA"),
                   "holds": (not ceiling) and gate("LORA2", "LORA") and x >= 0.15 and ci[0] > 0}
    if {"LORA2", "BASE"} <= E2.keys():
        x, ci = d("LORA2", "BASE", real, lambda r: sc(r["strict"]))
        P["R2"] = {"E2_real_net_LORA2_minus_BASE": [x, ci], "testable": gate("LORA2", "BASE"),
                   "holds": gate("LORA2", "BASE") and x > 0 and ci[0] > 0}
        x, ci = d("LORA2", "BASE", opU, ref)
        P["R5"] = {"E2_opera_U_refuse_LORA2_minus_BASE": [x, ci], "testable": not ceiling and gate("LORA2", "BASE"),
                   "holds": (not ceiling) and gate("LORA2", "BASE") and x >= 0.20}
    if out["E1"].get("IDK_LORA2") and out["E1"].get("IDK_LORA"):
        P["R3"] = {"E1_real_net_LORA2": out["E1"]["IDK_LORA2"]["real_net"], "E1_real_net_LORA": out["E1"]["IDK_LORA"]["real_net"],
                   "holds": out["E1"]["IDK_LORA2"]["real_net"] >= out["E1"]["IDK_LORA"]["real_net"] - 5}
    pn = raw / "normal_LORA2.jsonl"
    if pn.exists():
        rows = [r for r in map(json.loads, open(pn)) if not r["kind"].startswith("invented")]
        P["R4"] = {"refused": sum(r["refused"] for r in rows), "n": len(rows), "holds": sum(r["refused"] for r in rows) == 0}
    json.dump(out, open(HERE / a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
