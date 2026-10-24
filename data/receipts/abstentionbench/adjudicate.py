#!/usr/bin/env python3
"""PREREG_ABSTENTIONBENCH Addendum 1: blinded adjudication of the judge variants.
sample: frame = items where the exact, blind and norefs verdicts are not unanimous; 40 per label stratum (should-abstain,
  should-answer), at most 4 per dataset per stratum, plus 10 unanimous controls per stratum (at most 2 per dataset).
  Writes the blinded sheet (id, question, model answer only; answers over 3,000 characters shown as the first 1,800 and the
  last 1,000) and a separate key. Both stay in raw/ (local: they hold item text, and GPQA's terms forbid publishing it).
score: joins the adjudicator's labels (raw/ARM.adj_labels.jsonl: {"id", "abstained": true|false|null}) with the key.
Usage: adjudicate.py sample|score --checkout DIR --arm ARM [--seed N]"""
import argparse, json, math, random
from pathlib import Path
HERE = Path(__file__).resolve().parent; RAW = HERE / "raw"; VARS = ("exact", "blind", "norefs")
ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["sample", "score"]); ap.add_argument("--checkout", required=True)
ap.add_argument("--arm", required=True); ap.add_argument("--seed", type=int, default=20261024)
a = ap.parse_args()
load = lambda p: {(r["dataset"], r["index"]): r for r in map(json.loads, open(p)) if "error" not in r}
sheet, keyf, labf = RAW / f"{a.arm}.adj_sheet.jsonl", RAW / f"{a.arm}.adj_key.jsonl", RAW / f"{a.arm}.adj_labels.jsonl"

def draw(pool, n, cap, rng):
    pool = sorted(pool); rng.shuffle(pool); got, per = [], {}
    for k in pool:
        if len(got) == n: break
        if per.get(k[0], 0) < cap: got.append(k); per[k[0]] = per.get(k[0], 0) + 1
    return got

if a.cmd == "sample":
    if sheet.exists(): raise SystemExit(f"{sheet} exists; the sample is drawn once")
    items = load(Path(a.checkout) / "fast_subset.jsonl"); resp = load(RAW / f"{a.arm}.jsonl")
    J = {v: load(RAW / f"{a.arm}.judge_{v}.jsonl") for v in VARS}
    keys = [k for k in items if k in resp and all(k in J[v] and J[v][k]["verdict"] is not None for v in VARS)]
    split = lambda k: len({J[v][k]["verdict"] for v in VARS}) > 1
    rng = random.Random(a.seed); chosen = []
    for lab in (True, False):
        s = [k for k in keys if bool(items[k]["should_abstain"]) == lab]
        chosen += [(k, "disagree") for k in draw([k for k in s if split(k)], 40, 4, rng)]
        chosen += [(k, "control") for k in draw([k for k in s if not split(k)], 10, 2, rng)]
    rng.shuffle(chosen)
    with open(sheet, "w") as fs, open(keyf, "w") as fk:
        for n, (k, frame) in enumerate(chosen, 1):
            ans = resp[k]["content"] or ""
            if len(ans) > 3000: ans = ans[:1800] + "\n[... middle omitted ...]\n" + ans[-1000:]
            fs.write(json.dumps({"id": f"A{n:03d}", "question": items[k]["question"], "model_answer": ans}) + "\n")
            fk.write(json.dumps({"id": f"A{n:03d}", "dataset": k[0], "index": k[1], "frame": frame, "should_abstain": bool(items[k]["should_abstain"]),
                                 **{v: J[v][k]["verdict"] for v in VARS}}) + "\n")
    print(f"{len(chosen)} items -> {sheet.name} (blinded), {keyf.name} (key)")
else:
    key = {r["id"]: r for r in map(json.loads, open(keyf))}; lab = {r["id"]: r["abstained"] for r in map(json.loads, open(labf))}
    missing = [i for i in key if i not in lab]
    if missing: raise SystemExit(f"{len(missing)} ids unlabelled, e.g. {missing[:5]}")
    def wilson(k, n):
        if not n: return (None, None)
        p, z = k / n, 1.96; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return (round(c - h, 3), round(c + h, 3))
    out = {"arm": a.arm, "n": len(key), "unclear": sum(1 for v in lab.values() if v is None)}
    for frame in ("disagree", "control"):
        for stratum in ("all", "should_abstain", "should_answer"):
            ids = [i for i, r in key.items() if r["frame"] == frame and lab[i] is not None and (stratum == "all" or r["should_abstain"] == (stratum == "should_abstain"))]
            row = {"n": len(ids)}
            for v in VARS:
                k = sum(1 for i in ids if key[i][v] == lab[i]); row[v] = {"agree": k, "rate": round(k / len(ids), 3) if ids else None, "ci95": wilson(k, len(ids))}
            row["label_agrees_with_adjudicator"] = sum(1 for i in ids if key[i]["should_abstain"] == lab[i])
            out[f"{frame}/{stratum}"] = row
    json.dump(out, open(HERE / f"RESULT_{a.arm}_adjudication.json", "w"), indent=1); print(json.dumps(out, indent=1))
