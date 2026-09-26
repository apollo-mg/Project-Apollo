#!/usr/bin/env python3
"""Assemble corpus P0 (PREREG_PILOT.md): 40 E + 40 H + 40 U, 10 per template per arm, with IDENTICAL question
wording for real and fake items.

E/H: sampled with a fixed seed from the Wikidata pools (wikidata_pull.pools()); E = sitelinks >= 40, H = 3-8.
The answer entity's aliases (wbgetentities) are stored for grading. U: the web-PASS and Wikidata-clean fakes in
fakes_checks.jsonl. Writes P0.jsonl and prints the spot-check draw (4 per arm, seeded).
"""
import json, random, re, time
from pathlib import Path
import httpx
from wikidata_pull import pools, UA

HERE = Path(__file__).resolve().parent
SEED = 20260926
Q = {"capital": "What is the capital of {name}, an administrative region of {ctx}?",
     "novel": "In which year was the novel {name} by {ctx} first published?",
     "opera": "Who composed the opera {name}?",
     "university": "In which year was {name}, in {ctx}, founded?"}
# English articles, one rule for real and fake items alike (Wikidata labels carry none)
THE_COUNTRY = {"United States", "United Kingdom", "Netherlands", "Philippines", "Czech Republic", "Dominican Republic",
               "Bahamas", "Gambia", "Central African Republic", "Democratic Republic of the Congo",
               "Republic of the Congo", "United Arab Emirates", "Maldives", "Marshall Islands", "Solomon Islands",
               "Comoros", "Seychelles", "Vatican City"}
THE_INST = re.compile(r"^(University|Institute|College|School|Academy|Universit|Hochschule|Instituto|Istituto|Politecnico"
                      r"|Technische|Escuela|École|Ecole)| Institute of ")


def the_ctx(c):
    return f"the {c}" if c in THE_COUNTRY else c


def the_inst(n):
    return f"the {n}" if THE_INST.search(n) else n


def question(t, name, ctx):
    return Q[t].format(name=the_inst(name) if t == "university" else name, ctx=the_ctx(ctx))


ADJ2COUNTRY = {"Canadian": "Canada", "Venezuelan": "Venezuela", "Brazilian": "Brazil", "Italian": "Italy", "Spanish": "Spain",
               "Kenyan": "Kenya", "Norwegian": "Norway", "Nigerian": "Nigeria", "Peruvian": "Peru", "Swiss": "Switzerland",
               "Zambian": "Zambia",
               "Tanzanian": "Tanzania", "Philippine": "Philippines", "Croatian": "Croatia"}


def aliases(qids):
    out = {}
    for i in range(0, len(qids), 50):
        j = httpx.get("https://www.wikidata.org/w/api.php", params={"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                      "props": "labels|aliases", "languages": "en", "format": "json"}, headers=UA, timeout=60).json()
        for q, e in j.get("entities", {}).items():
            lab = e.get("labels", {}).get("en", {}).get("value")
            out[q] = ([lab] if lab else []) + [a["value"] for a in e.get("aliases", {}).get("en", [])]
        time.sleep(1)
    return out


def real_item(t, x, arm):
    name = x["itemLabel"]["value"]
    ctx = x.get("ctxLabel", {}).get("value", "")
    if t in ("novel", "university"):
        gold = x["ans"]["value"][:4]                                  # year of the date literal
        ans_qid = None
    else:
        gold = x["ansLabel"]["value"]
        ans_qid = x["ans"]["value"].rsplit("/", 1)[1]
    return {"arm": arm, "template": t, "question": question(t, name, ctx), "gold": gold, "ans_qid": ans_qid,
            "source": x["item"]["value"], "sitelinks": int(x["links"]["value"])}


def main():
    rng = random.Random(SEED)
    P = pools()
    items = []
    for t in Q:
        for arm in ("E", "H"):
            pool = sorted(P[t][arm], key=lambda x: x["item"]["value"])     # deterministic order before sampling
            items += [real_item(t, x, arm) for x in rng.sample(pool, 10)]
    fakes = [json.loads(l) for l in open(HERE / "fakes_checks.jsonl")]
    fakes = [f for f in fakes if f["web_verdict"] == "PASS"]
    assert all(f.get("wikidata_checked") for f in fakes), "run the Wikidata label check on every PASS fake first"
    fakes = [f for f in fakes if not f.get("wikidata_exact")]
    by_t = {}
    for f in fakes:
        by_t.setdefault(f["template"], []).append(f)
    for t in Q:
        assert len(by_t.get(t, [])) >= 10, (t, len(by_t.get(t, [])))
        for f in by_t[t][:10]:
            q0 = f["question"]                         # rebuilt from parts in the SHARED real/fake wording
            if t == "capital":
                ctx = next(c for a, c in ADJ2COUNTRY.items() if f" {a} " in q0)
            elif t == "novel":
                ctx = re.match(r".* by (.+) first published\?$", q0).group(1)
            elif t == "university":
                ctx = re.match(r".*, in (?:the )?(.+), founded\?$", q0).group(1)   # Wikidata labels carry no article
            else:
                ctx = ""
            q = question(t, f["name"], ctx)
            items.append({"arm": "U", "template": t, "question": q, "gold": "UNKNOWN", "ans_qid": None,
                          "source": "invented", "nonexistence": {"web": f["web_checked"], "wikidata": f.get("wikidata_checked")}})
    al = aliases(sorted({i["ans_qid"] for i in items if i["ans_qid"]}))
    for n, it in enumerate(items):
        it["id"] = f"P0-{it['arm']}-{it['template'][:3]}-{n:03d}"
        if it["ans_qid"]:
            it["gold_aliases"] = al.get(it["ans_qid"], [it["gold"]])
    with open(HERE / "P0.jsonl", "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(len(items), "items;", {a: sum(i["arm"] == a for i in items) for a in "EHU"})
    rs = random.Random(SEED + 1)
    print("\nSPOT-CHECK DRAW (4 per arm):")
    for a in "EHU":
        for it in rs.sample([i for i in items if i["arm"] == a], 4):
            print(f"  {it['id']}  {it['question']}  ->  {it['gold']}  [{it['source']}]")


if __name__ == "__main__":
    main()
