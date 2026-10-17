#!/usr/bin/env python3
"""Build the training pool for the idk-lora campaign (teach a small model to say UNKNOWN when it does not know).

Real Wikidata items only, from the quant-abstention corpus's cached SPARQL pools (corpus/raw/*.json: no new queries),
worded by build_p0's own question() and filtered by its own leaks(). Rules, and why:
- **No invented items.** Fakes carry their generator's tells; training on them could teach "refuse names that look
  generated" and score M1's invented items for the wrong reason. The refusal signal comes from real items the base
  model gets wrong, so M1's invented items measure transfer.
- **M1 is untouched:** any item whose Wikidata entity or question text appears in M1 is dropped.
- **One template held out:** `opera` is never trained on, so M1's opera cell measures transfer to an unseen question
  type.
- Sitelinks >= 3 across the whole range (famous to obscure), so the base model both knows and does not know items.
- At most CAP_DIV items share a country / author per template, so one country cannot dominate.
- Name answers get English aliases from wbgetentities (batched, cached in train_aliases.json) for grading. Year items
  skip P0's year-precision and lenient-year checks (network per item): a known source of label noise, which can only
  push training toward over-refusal and shows up as timidity on M1.
- Split by a seeded shuffle into `train` (80 %) and `calib` (20 %; fits the rung-1 logit bias, never trained on).

Writes train_pool.jsonl and train_build.json. Usage: build_train.py [--per-template N]
"""
import argparse, json, random, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent / "quant-abstention" / "corpus"
sys.path.insert(0, str(CORPUS))
import wikidata_pull as w   # noqa: E402
import build_p0 as b        # noqa: E402

SEED, HOLDOUT, CAP_DIV = 20261017, "opera", 15


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--per-template", type=int, default=1300); a = ap.parse_args()
    rng = random.Random(SEED)
    m1 = [json.loads(l) for l in open(CORPUS / "M1.jsonl")]
    m1_src = {i["source"] for i in m1 if i.get("source", "").startswith("http")}
    m1_q = {i["question"] for i in m1}
    w.HBAND = {t: (3, 39) for t in w.QUERIES}
    P = w.pools()
    log = {"seed": SEED, "holdout": HOLDOUT, "cap_div": CAP_DIV, "templates": {}}
    items = []
    for t in b.Q:
        if t == HOLDOUT: continue
        pool = sorted(P[t]["E"] + P[t]["H"], key=lambda x: x["item"]["value"])
        st = {"pool": len(pool)}
        pool = [x for x in pool if x["item"]["value"] not in m1_src]; st["after_m1_entity"] = len(pool)
        pool = [x for x in pool if not b.leaks(t, x)]; st["after_leak_filter"] = len(pool)
        rng.shuffle(pool)
        take, per = [], {}
        for x in pool:
            k = b.div_key(t, x)
            if per.get(k, 0) >= CAP_DIV: continue
            it = b.real_item(t, x, "T")
            if it["question"] in m1_q or it["gold"] is None: continue
            per[k] = per.get(k, 0) + 1; take.append(it)
            if len(take) >= a.per_template: break
        st["taken"] = len(take); st["sitelinks_ge40"] = sum(i["sitelinks"] >= 40 for i in take)
        log["templates"][t] = st; items += take
    al_path = HERE / "train_aliases.json"
    al = json.load(open(al_path)) if al_path.exists() else {}
    need = sorted({i["ans_qid"] for i in items if i["ans_qid"] and i["ans_qid"] not in al})
    if need:
        al.update(b.aliases(need)); json.dump(al, open(al_path, "w"), ensure_ascii=False)
    rng.shuffle(items)
    ncal = len(items) // 5
    for n, it in enumerate(items):
        it["id"] = f"T-{it['template'][:3]}-{n:04d}"
        it["split"] = "calib" if n < ncal else "train"
        if it["ans_qid"]:
            it["gold_aliases"] = al.get(it["ans_qid"]) or [it["gold"]]
    with open(HERE / "train_pool.jsonl", "w") as f:
        for it in items: f.write(json.dumps(it, ensure_ascii=False) + "\n")
    log["n"] = len(items); log["calib"] = ncal; log["train"] = len(items) - ncal
    json.dump(log, open(HERE / "train_build.json", "w"), indent=1)
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
