#!/usr/bin/env python3
"""Wikidata exact-label nonexistence check for every fake in fakes_checks.jsonl (rule wd in fakes.py). Resumable:
rows already carrying wikidata_checked are skipped; the file is rewritten after every row. Run from this directory."""
import json, time, httpx, unicodedata, sys
UA = {"User-Agent": "Apollo-quant-abstention/0.1 (local research; one request at a time)"}
norm = lambda s: unicodedata.normalize("NFKC", s).casefold().strip()
def search(name, lang):
    for attempt in range(8):
        try:
            r = httpx.get("https://www.wikidata.org/w/api.php", params={"action": "wbsearchentities", "search": name, "language": lang,
                          "limit": 10, "format": "json"}, headers=UA, timeout=30)
            j = r.json()
            if "error" not in j: return j.get("search", [])
            print("  api error", j["error"].get("code"), flush=True)
        except (ValueError, httpx.HTTPError) as e:
            print("  retry", type(e).__name__, r.status_code if 'r' in dir() else '', flush=True)
        time.sleep(20 * (attempt + 1))
    raise SystemExit(f"wikidata search failed for {name}")
rows = [json.loads(l) for l in open("fakes_checks.jsonl")]
for r in rows:
    if r.get("wikidata_checked"): continue
    hits = set()
    for lang in ("en", "de", "it", "fr", "es"):
        for h in search(r["name"], lang):
            labels = [h.get("label", "")] + [a for a in h.get("aliases", []) if isinstance(a, str)]
            if any(norm(x) == norm(r["name"]) for x in labels): hits.add(h["id"])
        time.sleep(1.0)
    r["wikidata_exact"] = sorted(hits); r["wikidata_checked"] = "2026-09-26 wbsearchentities en/de/it/fr/es"
    with open("fakes_checks.jsonl", "w") as f:
        for x in rows: f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"{r['name'][:40]:40s} {r['web_verdict']:7s} wikidata {sorted(hits)}", flush=True)
p = [r for r in rows if r["web_verdict"] == "PASS"]
print("FINAL: web PASS", len(p), "| Wikidata hits among them:", [(r["name"], r["wikidata_exact"]) for r in p if r["wikidata_exact"]])
