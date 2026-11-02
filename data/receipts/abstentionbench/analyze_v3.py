#!/usr/bin/env python3
"""PREREG_INSTRUMENT_V3.md: V1-V4 from raw/<ARM>.judge_v3.jsonl against each anchor's stored pass. Writes the committed,
text-free verdicts_<ARM>_v3.csv and RESULT_instrument_v3.json. Usage: analyze_v3.py   (stdlib only)"""
import csv, json
from pathlib import Path
AB = Path(__file__).resolve().parent; RAW = AB / "raw"
ANCHORS = ("LLAMA8", "L31AB", "Q27OFF", "Q27ON", "S25AB", "S26AB")
SUB = {(r["dataset"], r["index"]) for r in csv.DictReader(open(AB / "subset_1000.csv"))}


def load(f):
    return {(r["dataset"], str(r["index"])): r for r in map(json.loads, open(RAW / f)) if "error" not in r and (r["dataset"], str(r["index"])) in SUB}


def card(v):
    ab = [k for k in v if v[k]["should_abstain"]]; yes = [k for k in v if v[k]["verdict"] is True]
    return {"recall": round(sum(v[k]["verdict"] is True for k in ab) / len(ab), 4), "precision": round(sum(v[k]["should_abstain"] for k in yes) / len(yes), 4) if yes else None,
            "missing_info_recall": None, "n": len(v), "unparsed": sum(v[k]["verdict"] is None for k in v)}


def write_csv(arm, v):
    with open(AB / f"verdicts_{arm}_v3.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["dataset", "index", "should_abstain", "norefs"])
        for k in sorted(v): w.writerow([k[0], k[1], int(bool(v[k]["should_abstain"])), "" if v[k]["verdict"] is None else int(v[k]["verdict"])])


def main():
    res = {"anchors": {}}
    for arm in ANCHORS:
        old, new = load(f"{arm}.judge_norefs.jsonl"), load(f"{arm}.judge_v3.jsonl"); both = sorted(set(old) & set(new))
        flips = sum(old[k]["verdict"] != new[k]["verdict"] for k in both); co, cn = card({k: old[k] for k in both}), card({k: new[k] for k in both})
        res["anchors"][arm] = {"n": len(both), "flips": flips, "flip_rate": round(flips / len(both), 4), "stored": co, "v3": cn,
                               "d_recall": round(cn["recall"] - co["recall"], 4), "d_precision": round((cn["precision"] or 0) - (co["precision"] or 0), 4),
                               "hashed": sum("prompt_sha" in new[k] for k in both)}
        write_csv(arm, new)
        print(f"{arm}: n {len(both)}, flips {flips} ({100 * flips / len(both):.2f} %), recall {co['recall']} -> {cn['recall']}, precision {co['precision']} -> {cn['precision']}")
    dp, nv = load("L31AB.judge_dpin.jsonl"), load("L31AB.judge_v3.jsonl"); both = sorted(set(dp) & set(nv))
    res["V1_L31AB_v3_equals_dpin"] = [sum(dp[k]["verdict"] == nv[k]["verdict"] for k in both), len(both)]
    res["V2_max_flip_rate"] = max(a["flip_rate"] for a in res["anchors"].values())
    res["V3_max_abs_metric_change"] = max(max(abs(a["d_recall"]), abs(a["d_precision"])) for a in res["anchors"].values())
    subj = {(r["dataset"], str(r["index"])): r for r in map(json.loads, open(RAW / "L31V3.jsonl")) if "error" not in r}
    v31 = load("L31V3.judge_v3.jsonl"); write_csv("L31V3", v31)
    res["V4"] = {"rows": len(subj), "with_prompt_sha": sum("prompt_sha" in r for r in subj.values()), "card": card(v31),
                 "recall_vs_L31AB": round(card(v31)["recall"] - res["anchors"]["L31AB"]["stored"]["recall"], 4),
                 "distinct_prompts_vs_items": [len({r.get("prompt_sha") for r in subj.values()}), len(subj)]}
    json.dump(res, open(AB / "RESULT_instrument_v3.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "anchors"}, indent=1))


if __name__ == "__main__":
    main()
