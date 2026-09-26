#!/usr/bin/env python3
"""Assemble corpus P0 (PREREG_PILOT.md): 40 E + 40 H + 40 U, 10 per template per arm, with IDENTICAL question
wording for real and fake items. Writes P0.jsonl, P0_build.json (every filter count, every redraw) and prints the
spot-check draw (4 per arm, seeded).

Construction rules (all fixed before any model sees an item; none looks at a model):
- Pools (wikidata_pull.pools()): one row per (item, answer); items with more than one answer dropped; items whose
  item/answer/context entity has no English label dropped; labels unique within the template; E = sitelinks >= 40,
  H = 3-8, capital H = 3-20 (wikidata_pull.HBAND).
- Leak filter, real items only: an item is dropped when its answer is readable in its question -- the answer label
  and the item or context label share a word of 3+ letters (or a 5-letter stem) other than an administrative-type
  word (Pskov Oblast -> Pskov; Bender -> Bendery; "... of Luxembourg" -> Luxembourg), or
  a year gold appears in the item label, or the item label carries a parenthetical qualifier (metadata, not a name).
- Year golds (novel P577, university P571): the claim behind the gold must carry year precision or finer
  (Wikidata precision >= 9); a century- or decade-precision date is not a year. Checked on the sampled items;
  a failing item is replaced by the next one in the seeded shuffle, and the replacement is logged.
- Capital items (E and H) must be current administrative regions (check_current_admin); capital H items must not
  share their exact name with a famous entity, >= 40 sitelinks (check_namesake). Both run on sampled items, and a
  failing item is replaced like a precision failure.
- Sampling: each (template, arm) pool is sorted by QID, shuffled with one seeded RNG, and walked in order. At most
  CAP = 2 items per (template, arm) share a country (capital, university), an author (novel) or a composer (opera);
  the first build drew 4 Greek + 5 Ivorian capitals into capital-H and 3 Verdi + 3 Wagner into opera-E.
- Wording: one template per question type; English articles by one rule for real and fake items alike ("the
  United States", "the University of X", "the Altai Republic"), since Wikidata labels carry none.
- U items: the web-PASS fakes in fakes_checks.jsonl, every one Wikidata-checked (wd_labels.py) with no exact-label
  hit.
Every E/H item records its gold's source QID and Wikidata property; name golds also carry the answer entity's
English aliases (wbgetentities) for grading. Year items also carry `gold_years_lenient` (lenient_years(); descriptive
only, never a gate). The university template drops ", in <country>," when the country is already in the name.
"""
import json, random, re, time, unicodedata
from pathlib import Path
import httpx
from wikidata_pull import pools, UA

HERE = Path(__file__).resolve().parent
SEED = 20260926
API = "https://www.wikidata.org/w/api.php"
Q = {"capital": "What is the capital of {name}, an administrative region of {ctx}?",
     "novel": "In which year was the novel {name} by {ctx} first published?",
     "opera": "Who composed the opera {name}?",
     "university": "In which year was {name}, in {ctx}, founded?"}
PROP = {"capital": "P36", "novel": "P577", "opera": "P86", "university": "P571"}
YEAR = ("novel", "university")
# English articles, one rule for real and fake items alike (Wikidata labels carry none)
THE_COUNTRY = {"United States", "United Kingdom", "Netherlands", "Philippines", "Czech Republic", "Dominican Republic",
               "Bahamas", "Gambia", "Central African Republic", "Democratic Republic of the Congo",
               "Republic of the Congo", "United Arab Emirates", "Maldives", "Marshall Islands", "Solomon Islands",
               "Comoros", "Seychelles", "Vatican City", "People's Republic of China"}
THE_INST = re.compile(r"^(University|Institute|College|School|Academy|Universi|Hochschule|Instituto|Istituto|Politecnico"
                      r"|Technische|Escuela|École|Ecole|Museu)| Institute of | University of ")
THE_REGION = re.compile(r"^(Decentralized|Autonomous|Republic|Federal|Special)\b| Republic$")
CAP = 2   # at most this many items per (template, arm) share a country / author / composer
ADMIN = {"oblast", "krai", "region", "province", "prefecture", "state", "county", "district", "department",
         "governorate", "municipality", "territory", "republic", "autonomous", "community", "canton", "voivodeship",
         "city", "capital", "island", "islands", "division", "federal", "okrug", "raion", "parish", "emirate"}
ADJ2COUNTRY = {"Canadian": "Canada", "Venezuelan": "Venezuela", "Brazilian": "Brazil", "Italian": "Italy", "Spanish": "Spain",
               "Kenyan": "Kenya", "Norwegian": "Norway", "Nigerian": "Nigeria", "Peruvian": "Peru", "Swiss": "Switzerland",
               "Zambian": "Zambia", "Tanzanian": "Tanzania", "Philippine": "Philippines", "Croatian": "Croatia",
               "Russian": "Russia", "Argentine": "Argentina", "Polish": "Poland", "Romanian": "Romania",
               "Turkish": "Turkey", "Indonesian": "Indonesia", "Ghanaian": "Ghana", "Swedish": "Sweden",
               "Kazakh": "Kazakhstan", "Estonian": "Estonia", "Guinean": "Guinea", "Ecuadorian": "Ecuador",
               "Gabonese": "Gabon", "Congolese": "Republic of the Congo", "Chadian": "Chad", "Honduran": "Honduras",
               "Uzbek": "Uzbekistan", "Mexican": "Mexico"}


def the_ctx(c):
    return f"the {c}" if c in THE_COUNTRY else c


def the_inst(n):
    return f"the {n}" if THE_INST.search(n) else n


def question(t, name, ctx):
    if t == "university":
        if ctx and ctx in name:     # "the Academy of Internal Troops of Ukraine, in Ukraine" -> drop the repeated country
            return f"In which year was {the_inst(name)} founded?"
        name = the_inst(name)
    elif t == "capital" and THE_REGION.search(name):
        name = f"the {name}"
    return Q[t].format(name=name, ctx=the_ctx(ctx))


def div_key(t, x):
    return x["ans"]["value"] if t == "opera" else x.get("ctxLabel", {}).get("value", "")


def api(params):
    for attempt in range(8):
        try:
            j = httpx.get(API, params={**params, "format": "json"}, headers=UA, timeout=60).json()
            if "error" not in j:
                return j
        except (ValueError, httpx.HTTPError):   # a 429 comes back as non-JSON
            pass
        time.sleep(30 * (attempt + 1))
    raise SystemExit(f"wikidata api failed: {params.get('action')}")


STOP = {"the", "and", "del", "des", "les", "los", "las", "von", "van", "der", "den", "das", "die", "dos", "for"}


def words(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().casefold()
    return {w for w in re.findall(r"[a-z]+", s) if len(w) >= 3 and w not in ADMIN | STOP}


def shared(a, b):   # same word, or a spelling variant sharing a 5-letter stem (Bender / Bendery)
    return any(x == y or (len(x) >= 5 and len(y) >= 5 and x[:5] == y[:5]) for x in a for y in b)


def year_of(x):
    m = re.match(r"(\d{4})-", x["ans"]["value"])   # BCE dates and Wikidata "unknown value" (a genid URI) have no year gold
    return str(int(m.group(1))) if m else None


def leaks(t, x):
    item = x["itemLabel"]["value"]
    if "(" in item:        # a parenthetical qualifier is metadata, not a name: "Vadim (1832, unfinished; published in 1873)"
        return True
    if t in YEAR:
        return year_of(x) is None or year_of(x) in item
    ctx = x.get("ctxLabel", {}).get("value", "")    # the country can give the answer away too (Luxembourg)
    return shared(words(x["ansLabel"]["value"]), words(item) | words(ctx))


def year_precision(xs, prop):
    """{item QID: best precision among non-deprecated claims of `prop` whose year equals the gold}"""
    out = {}
    qids = [x["item"]["value"].rsplit("/", 1)[1] for x in xs]
    gold = {q: year_of(x) for q, x in zip(qids, xs)}
    for i in range(0, len(qids), 50):
        j = api({"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": "claims"})
        for q, e in j.get("entities", {}).items():
            vs = [c["mainsnak"]["datavalue"]["value"] for c in e.get("claims", {}).get(prop, [])
                  if c.get("rank") != "deprecated" and "datavalue" in c["mainsnak"]]
            ps = [v["precision"] for v in vs if str(int(v["time"][1:].split("-")[0])) == gold[q]]
            out[q] = max(ps, default=0)
        time.sleep(1)
    return out


NOT_CURRENT = re.compile(r"\bformer\b|\bdefunct\b|electoral|constituency|empire|military|NUTS|statistical|cohesion"
                         r"|annex|occupied|disputed|partially recogni[sz]ed", re.I)
ELECTORAL = re.compile(r"electoral|constituency", re.I)   # as a CLASS it is dual-use: Greenland and Kosrae are both


def qid(x):
    return x["item"]["value"].rsplit("/", 1)[1]


def check_year(xs, t):
    prec = year_precision(xs, PROP[t])
    return {qid(x): None if prec[qid(x)] >= 9 else f"year precision {prec[qid(x)]}" for x in xs}


def dissolved_after_founding(claims):
    """True when the latest dissolution (P576) is not followed by a re-founding (P571): Qashqadaryo was dissolved in
    1960 and re-established in 1964, and is current."""
    def years(p):
        return [int(c["mainsnak"]["datavalue"]["value"]["time"][:5]) for c in claims.get(p, [])
                if c.get("rank") != "deprecated" and "datavalue" in c["mainsnak"]]
    end, start = years("P576"), years("P571")
    return bool(end) and max(end) >= max(start, default=-10 ** 6)


def check_current_admin(xs, t):
    """Capital items must be current, uncontested administrative regions: not dissolved, and no 'former',
    historical-empire, electoral, military, statistical, annexed/occupied/disputed wording in the description or
    the P31 classes."""
    j = api({"action": "wbgetentities", "ids": "|".join(qid(x) for x in xs), "props": "descriptions|claims",
             "languages": "en"})["entities"]
    p31 = {q: [c["mainsnak"]["datavalue"]["value"]["id"] for c in e.get("claims", {}).get("P31", [])
               if "datavalue" in c["mainsnak"]] for q, e in j.items()}
    cls = sorted({c for cs in p31.values() for c in cs})
    lab = {}
    for i in range(0, len(cls), 50):
        for q, e in api({"action": "wbgetentities", "ids": "|".join(cls[i:i + 50]), "props": "labels",
                         "languages": "en"})["entities"].items():
            lab[q] = e.get("labels", {}).get("en", {}).get("value", "")
    out = {}
    for q, e in j.items():
        ended = dissolved_after_founding(e.get("claims", {}))
        desc = e.get("descriptions", {}).get("en", {}).get("value", "")
        bad = [w for w in [desc] if NOT_CURRENT.search(w)] + \
              [w for w in (lab.get(c, "") for c in p31[q]) if NOT_CURRENT.search(w) and not ELECTORAL.search(w)]
        out[q] = "dissolved (P576 after the latest P571)" if ended else (f"not current: {bad[0]}" if bad else None)
    time.sleep(1)
    return out


def check_namesake(xs, t):
    """A hard item's NAME must not be famous: drop it when any other Wikidata entity with the exact same English
    label or alias has >= 40 sitelinks (a 3-sitelink duplicate item of the Balearic Islands is not obscure)."""
    out = {}
    for x in xs:
        name = x["itemLabel"]["value"]
        hits = [h["id"] for h in api({"action": "wbsearchentities", "search": name, "language": "en", "limit": 10})
                .get("search", []) if h["id"] != qid(x) and any(norm(v) == norm(name) for v in
                [h.get("label", "")] + [a for a in h.get("aliases", []) if isinstance(a, str)])]
        top = 0
        if hits:
            ents = api({"action": "wbgetentities", "ids": "|".join(hits), "props": "sitelinks"})["entities"]
            top = max(len(e.get("sitelinks", {})) for e in ents.values())
        out[qid(x)] = f"famous namesake ({top} sitelinks)" if top >= 40 else None
        time.sleep(1)
    return out


def norm(s):
    return unicodedata.normalize("NFKC", s).casefold().strip()


def checks(t, arm):
    return ([check_year] if t in YEAR else []) + ([check_current_admin] if t == "capital" else []) + \
           ([check_namesake] if t == "capital" and arm == "H" else [])


def lenient_years(xs, t):
    """DESCRIPTIVE ONLY (the pilot's gates use the strict gold). Every year in a non-deprecated claim of the gold
    property on the item; for universities also the inception (P571) of entities it replaces (P1365) or follows
    (P155), since a founding date can belong to a predecessor (NTNU 1996 vs NTH 1910). One rule, applied at build
    time to every year item."""
    def years(claims, prop):
        return {int(c["mainsnak"]["datavalue"]["value"]["time"][1:].split("-")[0]) for c in claims.get(prop, [])
                if c.get("rank") != "deprecated" and "datavalue" in c["mainsnak"]}
    ents = api({"action": "wbgetentities", "ids": "|".join(qid(x) for x in xs), "props": "claims"})["entities"]
    out = {q: years(e.get("claims", {}), PROP[t]) for q, e in ents.items()}
    if t == "university":
        pred = {q: [c["mainsnak"]["datavalue"]["value"]["id"] for k in ("P1365", "P155")
                    for c in e.get("claims", {}).get(k, []) if "datavalue" in c["mainsnak"]] for q, e in ents.items()}
        ids = sorted({p for ps in pred.values() for p in ps})
        py = {}
        for i in range(0, len(ids), 50):
            for q, e in api({"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]), "props": "claims"})["entities"].items():
                py[q] = years(e.get("claims", {}), "P571")
        for q in out:
            for p in pred[q]:
                out[q] |= py.get(p, set())
    time.sleep(1)
    return {q: sorted(str(y) for y in v) for q, v in out.items()}


def aliases(qids):
    out = {}
    for i in range(0, len(qids), 50):
        j = api({"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": "labels|aliases", "languages": "en"})
        for q, e in j.get("entities", {}).items():
            lab = e.get("labels", {}).get("en", {}).get("value")
            out[q] = ([lab] if lab else []) + [a["value"] for a in e.get("aliases", {}).get("en", [])]
        time.sleep(1)
    return out


def real_item(t, x, arm):
    name = x["itemLabel"]["value"]
    ctx = x.get("ctxLabel", {}).get("value", "")
    if t in YEAR:
        gold, ans_qid = year_of(x), None
    else:
        gold, ans_qid = x["ansLabel"]["value"], x["ans"]["value"].rsplit("/", 1)[1]
    return {"arm": arm, "template": t, "question": question(t, name, ctx), "gold": gold, "ans_qid": ans_qid,
            "source": x["item"]["value"], "property": PROP[t], "sitelinks": int(x["links"]["value"])}


def main():
    rng = random.Random(SEED)
    P = pools()
    log = {"seed": SEED, "pools": {}, "leak_dropped_examples": {}, "redraws": []}
    items = []
    for t in Q:
        for arm in ("E", "H"):
            pool = sorted(P[t][arm], key=lambda x: x["item"]["value"])     # deterministic order before shuffling
            clean = [x for x in pool if not leaks(t, x)]
            log["pools"][f"{t}/{arm}"] = {"pool": len(pool), "after_leak_filter": len(clean)}
            log["leak_dropped_examples"][f"{t}/{arm}"] = [(x["itemLabel"]["value"], x.get("ansLabel", x["ans"])["value"])
                                                         for x in pool if leaks(t, x)][:8]
            assert len(clean) >= 10, (t, arm, len(clean), "pool too small after the leak filter: stop and ask")
            rng.shuffle(clean)
            take, k, capped = [], 0, 0
            while len(take) < 10:
                batch = []
                while len(batch) < 10 - len(take) and k < len(clean):
                    x, k = clean[k], k + 1
                    if sum(div_key(t, y) == div_key(t, x) for y in take + batch) >= CAP:
                        capped += 1
                        continue
                    batch.append(x)
                assert batch, (t, arm, "pool exhausted by the item checks")
                for check in checks(t, arm):
                    why = check(batch, t)
                    for x in batch:
                        if why[qid(x)]:
                            log["redraws"].append({"template": t, "arm": arm, "item": qid(x),
                                                   "label": x["itemLabel"]["value"], "reason": why[qid(x)]})
                    batch = [x for x in batch if not why[qid(x)]]
                take += batch
            log["pools"][f"{t}/{arm}"]["skipped_by_diversity_cap"] = capped
            new = [real_item(t, x, arm) for x in take]
            if t in YEAR:
                ly = lenient_years(take, t)
                for it, x in zip(new, take):
                    it["gold_years_lenient"] = sorted(set(ly[qid(x)]) | {it["gold"]}, key=int)
            items += new
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
                ctx = re.match(r".*, in (?:the )?(.+), founded\?$", q0).group(1)   # the article is re-added by rule
            else:
                ctx = ""
            items.append({"arm": "U", "template": t, "question": question(t, f["name"], ctx), "gold": "UNKNOWN",
                          "ans_qid": None, "source": "invented",
                          "nonexistence": {"web": f["web_checked"], "web_queries": [q["query"] for q in f["web_queries"]],
                                           "wikidata": f["wikidata_checked"]}})
    al = aliases(sorted({i["ans_qid"] for i in items if i["ans_qid"]}))
    for n, it in enumerate(items):
        it["id"] = f"P0-{it['arm']}-{it['template'][:3]}-{n:03d}"
        if it["ans_qid"]:
            it["gold_aliases"] = al.get(it["ans_qid"], [it["gold"]])
    with open(HERE / "P0.jsonl", "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    json.dump(log, open(HERE / "P0_build.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(log["pools"]))
    print("redraws:", len(log["redraws"]))
    for r in log["redraws"]:
        print(f"   {r['template']}/{r['arm']}  {r['label'][:40]:40s} {r['reason'][:70]}")
    print(len(items), "items;", {a: sum(i["arm"] == a for i in items) for a in "EHU"})
    rs = random.Random(SEED + 1)
    print("\nSPOT-CHECK DRAW (4 per arm):")
    for a in "EHU":
        for it in rs.sample([i for i in items if i["arm"] == a], 4):
            print(f"  {it['id']}  {it['question']}  ->  {it['gold']}  [{it['source']}]")


if __name__ == "__main__":
    main()
