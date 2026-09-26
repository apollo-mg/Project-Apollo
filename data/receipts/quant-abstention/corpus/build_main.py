#!/usr/bin/env python3
"""Assemble the main-campaign corpus M1: 40 E + 100 H + 100 U. Writes M1.jsonl and M1_build.json.

Every construction rule is build_p0's own code (imported, not copied): question wording and articles, the leak
filter, the item checks (year precision, current administrative region, famous namesake), the diversity cap, the
aliases and the lenient year sets. What differs from P0, and why:
- E: the 40 P0 easy items, verbatim (audited, and E passed P3 in the pilot). `p0_id` keeps the link.
- H: 25 per template, freshly drawn at sitelinks 9-39 for every template, from a new seed. That is everything
  between the pilot's hard band and the easy band. The pilot's P3 moved the band, and 9-20 was tried first, but a
  dry run left capitals only 22 drawable items under the diversity cap (PREREG_MAIN).
- U: the first 25 web-PASS, Wikidata-clean fakes per template in fakes.py order (P0's 10, then the main batch).
"""
import json, random
from pathlib import Path
import wikidata_pull as w
import build_p0 as b

HERE = Path(__file__).resolve().parent
SEED = 20260927
PER_T_H, PER_T_U = 25, 25
H_BAND = (9, 39)


def main():
    rng = random.Random(SEED)
    w.HBAND = {t: H_BAND for t in w.QUERIES}
    P = w.pools()
    log = {"seed": SEED, "h_band": H_BAND, "pools": {}, "leak_dropped_examples": {}, "redraws": []}
    items = []
    # E: verbatim from P0
    for it in map(json.loads, open(HERE / "P0.jsonl")):
        if it["arm"] == "E":
            it = dict(it, p0_id=it["id"])
            items.append(it)
    # H: fresh draw, same rules as P0
    for t in b.Q:
        pool = sorted(P[t]["H"], key=lambda x: x["item"]["value"])
        clean = [x for x in pool if not b.leaks(t, x)]
        log["pools"][f"{t}/H"] = {"pool": len(pool), "after_leak_filter": len(clean)}
        log["leak_dropped_examples"][f"{t}/H"] = [(x["itemLabel"]["value"], x.get("ansLabel", x["ans"])["value"])
                                                 for x in pool if b.leaks(t, x)][:8]
        rng.shuffle(clean)
        take, k, capped = [], 0, 0
        while len(take) < PER_T_H:
            batch = []
            while len(batch) < PER_T_H - len(take) and k < len(clean):
                x, k = clean[k], k + 1
                if sum(b.div_key(t, y) == b.div_key(t, x) for y in take + batch) >= b.CAP:
                    capped += 1
                    continue
                batch.append(x)
            assert batch, (t, "pool exhausted by the item checks")
            for check in b.checks(t, "H"):
                why = check(batch, t)
                for x in batch:
                    if why[b.qid(x)]:
                        log["redraws"].append({"template": t, "arm": "H", "item": b.qid(x),
                                               "label": x["itemLabel"]["value"], "reason": why[b.qid(x)]})
                batch = [x for x in batch if not why[b.qid(x)]]
            take += batch
        log["pools"][f"{t}/H"]["skipped_by_diversity_cap"] = capped
        new = [b.real_item(t, x, "H") for x in take]
        if t in b.YEAR:
            ly = b.lenient_years(take, t)
            for it, x in zip(new, take):
                it["gold_years_lenient"] = sorted(set(ly[b.qid(x)]) | {it["gold"]}, key=int)
        items += new
    # U: first 25 clean fakes per template
    fakes = [json.loads(l) for l in open(HERE / "fakes_checks.jsonl")]
    fakes = [f for f in fakes if f["web_verdict"] == "PASS"]
    assert all(f.get("wikidata_checked") for f in fakes), "run wd_labels.py on every PASS fake first"
    fakes = [f for f in fakes if not f.get("wikidata_exact")]
    for t in b.Q:
        ft = [f for f in fakes if f["template"] == t]
        assert len(ft) >= PER_T_U, (t, len(ft))
        for f in ft[:PER_T_U]:
            q0 = f["question"]
            if t == "capital":
                ctx = next(c for a, c in b.ADJ2COUNTRY.items() if f" {a} " in q0)
            elif t == "novel":
                ctx = b.re.match(r".* by (.+) first published\?$", q0).group(1)
            elif t == "university":
                ctx = b.re.match(r".*, in (?:the )?(.+), founded\?$", q0).group(1)
            else:
                ctx = ""
            items.append({"arm": "U", "template": t, "question": b.question(t, f["name"], ctx), "gold": "UNKNOWN",
                          "ans_qid": None, "source": "invented",
                          "nonexistence": {"web": f["web_checked"], "web_queries": [q["query"] for q in f["web_queries"]],
                                           "wikidata": f["wikidata_checked"]}})
    al = b.aliases(sorted({i["ans_qid"] for i in items if i["ans_qid"] and "gold_aliases" not in i}))
    for n, it in enumerate(items):
        it["id"] = f"M1-{it['arm']}-{it['template'][:3]}-{n:03d}"
        if it["ans_qid"] and "gold_aliases" not in it:
            it["gold_aliases"] = al.get(it["ans_qid"], [it["gold"]])
    with open(HERE / "M1.jsonl", "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    json.dump(log, open(HERE / "M1_build.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(log["pools"]))
    print("redraws:", len(log["redraws"]))
    for r in log["redraws"]:
        print(f"   {r['template']}/{r['arm']}  {r['label'][:40]:40s} {r['reason'][:70]}")
    print(len(items), "items;", {a: sum(i["arm"] == a for i in items) for a in "EHU"})


if __name__ == "__main__":
    main()
