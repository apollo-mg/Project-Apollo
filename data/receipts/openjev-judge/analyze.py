#!/usr/bin/env python3
"""PREREG_OPENJEV_JUDGE.md: score J1-J6 and the secondaries from raw/*.jsonl -> RESULT_openjev_judge.json + stdout."""
import json, random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = {"OJ-0.8B": "raw/openjev_qwen3.5-0.8b-nli-v5.jsonl", "OJ-2B": "raw/openjev_qwen3.5-2b-nli-v5.jsonl",
        "OJ-4B": "raw/openjev_qwen3.5-4b-nli-v5.jsonl", "QJ": "raw/judge_qwen38-27b-iq3xxs.jsonl"}
B = 10_000


def load(path):
    rows = {}
    for l in open(HERE / path):
        r = json.loads(l)
        if r.get("id"):
            rows[(r["id"], r["cond"], r["wording"])] = r
    return rows


def auroc(pairs):
    """pairs: [(p_ask, is_ask)]. Mann-Whitney with ties counted half."""
    pos = [p for p, y in pairs if y]
    neg = [p for p, y in pairs if not y]
    if not pos or not neg:
        return None
    s = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return s / (len(pos) * len(neg))


def bal_acc(pairs, thr=0.5):
    pos = [p for p, y in pairs if y]
    neg = [p for p, y in pairs if not y]
    return 0.5 * (sum(p > thr for p in pos) / len(pos) + sum(p <= thr for p in neg) / len(neg))


def ece(pairs, bins=10):
    tot, e = len(pairs), 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(p, y) for p, y in pairs if (lo <= p < hi) or (b == bins - 1 and p == 1.0)]
        if sel:
            e += len(sel) / tot * abs(sum(p for p, _ in sel) / len(sel) - sum(y for _, y in sel) / len(sel))
    return e


def main():
    items = [json.loads(l) for l in open(HERE / "items.jsonl")]
    clusters = defaultdict(list)
    for it in items:
        clusters[it["cluster"]].append(it["id"])
    cl_ids = sorted(clusters)
    gold = {it["id"]: it["gold"] == "ask" for it in items}
    cls = {it["id"]: it["class"] for it in items}
    arms = {a: load(p) for a, p in ARMS.items() if (HERE / p).exists()}
    for a in list(arms):   # an arm still running is left out, never scored on a partial set
        if len(arms[a]) < 4 * len(gold):
            print(f"(skipping {a}: {len(arms[a])}/{4 * len(gold)} rows)"); del arms[a]

    def score(arm, cond, w):
        return {i: arms[arm][(i, cond, w)]["p_ask"] for i in gold}

    rng = random.Random(20260925)
    resamples = [[c for _ in cl_ids for c in [rng.choice(cl_ids)]] for _ in range(B)]

    def boot(fn):
        vals = []
        for rs in resamples:
            ids = [i for c in rs for i in clusters[c]]
            v = fn(ids)
            if v is not None:
                vals.append(v)
        vals.sort()
        return [vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]], len(vals)

    def auc_ids(sc, ids):
        return auroc([(sc[i], gold[i]) for i in ids])

    res = {"n_items": len(items), "n_ask": sum(gold.values()), "n_clusters": len(cl_ids), "arms": {}}
    S = {}
    for arm in arms:
        for cond in ("world", "reqonly"):
            for w in ("W1", "W2"):
                sc = score(arm, cond, w); S[(arm, cond, w)] = sc
                pairs = [(sc[i], gold[i]) for i in gold]
                ci, nb = boot(lambda ids, sc=sc: auc_ids(sc, ids))
                d = {"auroc": auroc(pairs), "auroc_ci95": ci, "bal_acc@0.5": bal_acc(pairs), "ece10": ece(pairs),
                     "mean_p_ask_gold_ask": sum(sc[i] for i in gold if gold[i]) / sum(gold.values()),
                     "mean_p_ask_gold_act": sum(sc[i] for i in gold if not gold[i]) / sum(not g for g in gold.values())}
                if arm.startswith("OJ"):   # neutral mass, averaged over the two option hypotheses
                    neu = {i: sum(t[2] for t in arms[arm][(i, cond, w)]["triples"].values()) / 2 for i in gold}
                    d["mean_neutral_gold_ask"] = sum(neu[i] for i in gold if gold[i]) / sum(gold.values())
                    d["mean_neutral_gold_act"] = sum(neu[i] for i in gold if not gold[i]) / sum(not g for g in gold.values())
                if arm == "QJ":
                    d["min_letter_mass"] = min(o["mass"] for i in gold for o in arms[arm][(i, cond, w)]["orders"])
                res["arms"][f"{arm}|{cond}|{w}"] = d

    def diff(a, b):
        sa, sb = S[a], S[b]
        point = auroc([(sa[i], gold[i]) for i in gold]) - auroc([(sb[i], gold[i]) for i in gold])
        ci, _ = boot(lambda ids: (lambda x, y: None if x is None or y is None else x - y)(auc_ids(sa, ids), auc_ids(sb, ids)))
        return {"diff": point, "ci95": ci}

    pred = {}
    g = lambda arm, cond="world", w="W1": res["arms"].get(f"{arm}|{cond}|{w}")
    if "OJ-4B" in arms:
        pred["J1 OJ-4B W1 world AUROC >= 0.70"] = {"auroc": g("OJ-4B")["auroc"], "held": g("OJ-4B")["auroc"] >= 0.70}
        d = diff(("OJ-4B", "world", "W1"), ("OJ-4B", "reqonly", "W1"))
        pred["J2 OJ-4B world - reqonly > 0, CI lo > 0"] = {**d, "held": d["ci95"][0] > 0}
    if "QJ" in arms:
        pred["J3 QJ W1 world AUROC >= 0.80"] = {"auroc": g("QJ")["auroc"], "held": g("QJ")["auroc"] >= 0.80}
        if "OJ-4B" in arms:
            d = diff(("QJ", "world", "W1"), ("OJ-4B", "world", "W1"))
            pred["J4 QJ - OJ-4B (world, W1) > 0, CI lo > 0"] = {**d, "held": d["ci95"][0] > 0}
        agent = {json.loads(l)["id"]: json.loads(l) for l in open(HERE / "../argus-v5/raw/val_OFF-s1.jsonl")}
        over = [i for i in gold if gold[i] and agent[i]["actions"]]
        hit = [i for i in over if S[("QJ", "world", "W1")][i] > 0.5]
        pred["J5 QJ P(ask)>0.5 on >=10 of the agent's over-acted ask items"] = {
            "n_over_acted": len(over), "judge_says_ask": len(hit), "held": len(hit) >= 10,
            "items": {i: round(S[("QJ", "world", "W1")][i], 3) for i in over}}
        acted = {i: bool(agent[i]["actions"]) for i in gold}
        res["agent_reference"] = {"acted_on_act": sum(acted[i] for i in gold if not gold[i]),
                                  "acted_on_ask": sum(acted[i] for i in gold if gold[i]),
                                  "bal_acc": 0.5 * (sum(acted[i] for i in gold if not gold[i]) / 47
                                                    + sum(not acted[i] for i in gold if gold[i]) / 30)}
    oj = [a for a in ("OJ-0.8B", "OJ-2B", "OJ-4B") if a in arms]
    if len(oj) == 3:
        v = [g(a)["auroc"] for a in oj]
        pred["J6 OJ AUROC 0.8B <= 2B <= 4B (descriptive)"] = {"aurocs": dict(zip(oj, v)), "held": v[0] <= v[1] <= v[2]}
    res["predictions"] = pred
    for arm in arms:   # secondaries: wording sensitivity, per-class AUROC
        res["arms"][f"{arm}|world|W1"]["W1_minus_W2"] = diff((arm, "world", "W1"), (arm, "world", "W2"))
        sc = S[(arm, "world", "W1")]
        per = {}
        for c in sorted(set(cls.values())):
            ids = [i for i in gold if cls[i] == c]
            per[c] = {"n_ask": sum(gold[i] for i in ids), "n_act": sum(not gold[i] for i in ids),
                      "auroc": auc_ids(sc, ids)}
        res["arms"][f"{arm}|world|W1"]["per_class"] = per
    json.dump(res, open(HERE / "RESULT_openjev_judge.json", "w"), indent=1)

    print(f"{'arm|cond|wording':24s} {'AUROC':>6s}  {'95% CI':>14s}  {'balacc':>6s} {'ECE':>5s}  {'P(ask)|ask':>10s} {'P(ask)|act':>10s}")
    for k, d in res["arms"].items():
        print(f"{k:24s} {d['auroc']:6.3f}  [{d['auroc_ci95'][0]:.3f},{d['auroc_ci95'][1]:.3f}]  {d['bal_acc@0.5']:6.3f} "
              f"{d['ece10']:5.3f}  {d['mean_p_ask_gold_ask']:10.3f} {d['mean_p_ask_gold_act']:10.3f}")
    print(json.dumps(res.get("agent_reference")))
    for k, v in pred.items():
        print(k, "->", {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != "items"})


if __name__ == "__main__":
    main()
