#!/usr/bin/env python3
"""Build the blind A/B rating page for PREREG_HEMM_TECHWRITING.md.
Side assignment is random per task (seeded) and written ONLY to raw/ab_mapping.json -- never into the page."""
import html, json, random
from pathlib import Path

HERE = Path(__file__).parent
tasks = [t for t in json.load(open(HERE / "tasks.json"))["tasks"] if t["kind"] != "ledger"]
rows = {}
for arm in ("S5", "H5"):
    for l in open(HERE / "raw" / f"{arm}.jsonl"):
        r = json.loads(l); rows[(arm, r["id"])] = r

rng = random.Random(20260924)
mapping, items = {}, []
for t in tasks:
    s5, h5 = rows[("S5", t["id"])], rows[("H5", t["id"])]
    h_is_a = rng.random() < 0.5
    mapping[t["id"]] = {"A": "H5" if h_is_a else "S5", "B": "S5" if h_is_a else "H5"}
    a, b = (h5, s5) if h_is_a else (s5, h5)
    head = t["prompt"].split("\n\n")[0] if t.get("source") else t["user_prompt"]
    items.append({"id": t["id"], "kind": t["kind"], "ask": head, "source": t.get("source") or "",
                  "A": a.get("content", ""), "B": b.get("content", "")})
(HERE / "raw").mkdir(exist_ok=True)
json.dump(mapping, open(HERE / "raw" / "ab_mapping.json", "w"), indent=1)

KIND = {"summary": "Summary", "bug_report": "Bug report", "docs": "Documentation", "explain": "Explainer",
        "clarity": "Clarity rewrite"}
for it in items:
    it["kindLabel"] = KIND[it["kind"]]
data = json.dumps(items).replace("</", "<\\/")
page = (HERE / "page_template.html").read_text().replace("/*__DATA__*/[]", data)
(HERE / "rating_page.html").write_text(page)
print(f"page: {len(items)} tasks, {len(page)//1024} KB; mapping -> raw/ab_mapping.json "
      f"(H5 is A on {sum(v['A']=='H5' for v in mapping.values())} of {len(mapping)})")
