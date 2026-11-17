#!/usr/bin/env python3
"""M1 item audit, step 2: for each flagged REAL item, what Wikidata says today (every statement of the item's property,
with its rank and point-in-time qualifiers) and what the English Wikipedia infobox says (a second source).
Reads flags.json, writes evidence_real.json. Network: the public Wikidata and Wikipedia APIs only.
Usage: verify_real.py"""
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ITEMS = {json.loads(l)["id"]: json.loads(l) for l in open(HERE.parent / "quant-abstention" / "corpus" / "M1.jsonl")}
PROP = {"capital": "P36", "university": "P571", "novel": "P577", "opera": "P86"}
INFOBOX = re.compile(r"^\s*\|\s*(established|founded|opened|chartered|foundation|release_date|pub_date|published|"
                     r"first_published|composer|seat|capital|capital_city|admin_center|seat_type)\s*=\s*(.+)$", re.I | re.M)
UA = {"User-Agent": "abstend-item-audit/0.1 (research script)"}


LABELS = {}


def get(url, tries=6):
    """GET with backoff: Wikimedia answers 429 when requests come too fast; honour Retry-After."""
    for n in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or n == tries - 1:
                raise
            time.sleep(min(int(e.headers.get("Retry-After") or 10), 60) + 2 * n)


def labels(qids):
    """English labels for many items, 50 per request, cached."""
    todo = sorted({q for q in qids if q not in LABELS})
    for i in range(0, len(todo), 50):
        d = get("https://www.wikidata.org/w/api.php?action=wbgetentities&props=labels&languages=en&format=json&ids=" + "|".join(todo[i:i + 50]))
        for q, e in d["entities"].items():
            LABELS[q] = e.get("labels", {}).get("en", {}).get("value", q)
        time.sleep(1)


def label(qid):
    if qid not in LABELS:
        labels([qid])
    return LABELS[qid]


def value(snak):
    dv = snak.get("datavalue", {}).get("value")
    if isinstance(dv, dict) and "id" in dv:
        return label(dv["id"])
    if isinstance(dv, dict) and "time" in dv:
        return dv["time"].lstrip("+")[:{9: 4, 10: 7, 11: 10}.get(dv.get("precision"), 10)]
    return str(dv)


def main():
    flags = json.load(open(HERE / "flags.json"))["flags"]
    real = [f for f in flags if f["group"] != "invented"]
    qids = sorted({ITEMS[f["id"]]["source"].rsplit("/", 1)[-1] for f in real})
    ENT = {}
    for i in range(0, len(qids), 50):        # every subject in one request: claims and the enwiki sitelink
        d = get("https://www.wikidata.org/w/api.php?action=wbgetentities&props=claims|sitelinks&sitefilter=enwiki&format=json&ids=" + "|".join(qids[i:i + 50]))
        ENT.update(d["entities"])
    vals = [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for f in real for c in
            ENT[ITEMS[f["id"]]["source"].rsplit("/", 1)[-1]].get("claims", {}).get(PROP[ITEMS[f["id"]]["template"]], [])]
    labels([v for v in vals if isinstance(v, str)])
    out = []
    for f in flags:
        if f["group"] == "invented":
            continue
        it = ITEMS[f["id"]]
        qid = it["source"].rsplit("/", 1)[-1]
        prop = PROP[it["template"]]
        ent = ENT[qid]
        stmts = []
        for c in ent.get("claims", {}).get(prop, []):
            q = c.get("qualifiers", {})
            quals = {k: [value(s) for s in q[k]] for k in ("P580", "P582", "P585") if k in q}
            stmts.append({"value": value(c["mainsnak"]), "rank": c["rank"], "qualifiers": quals, "refs": len(c.get("references", []))})
        title = ent.get("sitelinks", {}).get("enwiki", {}).get("title")
        wp = []
        if title:
            p = get("https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext&section=0&format=json&page=" + urllib.parse.quote(title))
            text = p.get("parse", {}).get("wikitext", {}).get("*", "")
            wp = [f"{m.group(1)} = {m.group(2).strip()[:90]}" for m in INFOBOX.finditer(text)]
        out.append({"id": f["id"], "question": it["question"], "gold": it["gold"], "consensus": f["consensus"],
                    "consensus_n": f["consensus_n"], "correct": f["correct"], "qid": qid, "prop": prop,
                    "wikidata": stmts, "enwiki": title, "infobox": wp})
        time.sleep(1.5)
    (HERE / "evidence_real.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for e in out:
        wd = "; ".join(f"{s['value']} ({s['rank']}{', ' + json.dumps(s['qualifiers'], ensure_ascii=False) if s['qualifiers'] else ''}, refs {s['refs']})" for s in e["wikidata"])
        print(f"{e['id']} gold={e['gold']!r} models={e['consensus']!r}x{e['consensus_n']} correct={e['correct']}\n   Q: {e['question'][:110]}\n   WD {e['prop']}: {wd}\n   WP {e['enwiki']}: {' | '.join(e['infobox'])[:300]}")


if __name__ == "__main__":
    main()
