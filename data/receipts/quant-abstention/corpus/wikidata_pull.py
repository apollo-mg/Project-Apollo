#!/usr/bin/env python3
"""Pull the real-item pools for the quant-abstention corpus from Wikidata (DESIGN.md, PREREG_PILOT.md).

One query at a time, spaced out, retrying on 429 with backoff. Raw results are cached in raw/<template>.json (with
the query text and fetch time) so a re-run never re-queries. Pools are then filtered to single-valued answers and
labels unique within the template, and split by sitelink count: E >= 40, H 3-8. The split is model-independent.
"""
import datetime as dt, json, time
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"; RAW.mkdir(exist_ok=True)
UA = {"User-Agent": "Apollo-quant-abstention/0.1 (local research; one query at a time)",
      "Accept": "application/sparql-results+json"}
LABEL = 'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }'
QUERIES = {
    "capital": f"""SELECT ?item ?itemLabel ?ans ?ansLabel ?ctxLabel ?links WHERE {{
        ?item wdt:P36 ?ans; wdt:P131 ?ctx; wikibase:sitelinks ?links. ?ctx wdt:P31 wd:Q6256.
        FILTER NOT EXISTS {{ ?item wdt:P576 ?e }} {LABEL} }}""",   # first-level: located directly in a country
    "novel": f"""SELECT ?item ?itemLabel ?ans ?ctx ?ctxLabel ?links WHERE {{
        ?item wdt:P7937 wd:Q8261; wdt:P50 ?ctx; wdt:P577 ?ans; wikibase:sitelinks ?links.   # form of creative work = novel
        FILTER(?links >= 3) {LABEL} }}""",
    "opera": f"""SELECT ?item ?itemLabel ?ans ?ansLabel ?links WHERE {{
        {{ ?item wdt:P31 wd:Q1344 }} UNION {{ ?item wdt:P7937 wd:Q1344 }} ?item wdt:P86 ?ans; wikibase:sitelinks ?links.
        FILTER(?links >= 3) {LABEL} }}""",
    "university": f"""SELECT ?item ?itemLabel ?ans ?ctxLabel ?links WHERE {{
        ?item wdt:P31 wd:Q3918; wdt:P571 ?ans; wdt:P17 ?ctx; wikibase:sitelinks ?links.
        FILTER(?links >= 3) {LABEL} }}""",
}


def fetch(name, q):
    out = RAW / f"{name}.json"
    if out.exists():
        return json.load(open(out))["rows"]
    for attempt in range(8):
        r = httpx.get("https://query.wikidata.org/sparql", params={"query": q}, headers=UA, timeout=300)
        if r.status_code == 200:
            rows = r.json()["results"]["bindings"]
            json.dump({"query": q, "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                       "rows": rows}, open(out, "w"))
            return rows
        wait = int(r.headers.get("retry-after", 0) or 0) or 30 * (attempt + 1)
        print(f"  {name}: http {r.status_code}, waiting {wait}s", flush=True)
        time.sleep(wait)
    raise SystemExit(f"{name}: gave up")


def pools():
    P = {}
    for name, q in QUERIES.items():
        rows = fetch(name, q)
        n = {}
        for x in rows:
            n[x["item"]["value"]] = n.get(x["item"]["value"], 0) + 1
        bare = lambda x, k: k in x and x[k]["value"][:1] == "Q" and x[k]["value"][1:].isdigit()   # no English label
        single = [x for x in rows if n[x["item"]["value"]] == 1
                  and not any(bare(x, k) for k in ("itemLabel", "ansLabel", "ctxLabel"))]
        lab = {}
        for x in single:
            lab[x["itemLabel"]["value"]] = lab.get(x["itemLabel"]["value"], 0) + 1
        uniq = [x for x in single if lab[x["itemLabel"]["value"]] == 1]
        P[name] = {"E": [x for x in uniq if int(x["links"]["value"]) >= 40],
                   "H": [x for x in uniq if 3 <= int(x["links"]["value"]) <= 8]}
        print(f"{name:10s} rows {len(rows):6d} usable {len(uniq):5d}  E {len(P[name]['E']):4d}  H {len(P[name]['H']):5d}", flush=True)
        time.sleep(65)   # the query service budgets compute per minute; heavy queries back to back get 429
    return P


if __name__ == "__main__":
    pools()
