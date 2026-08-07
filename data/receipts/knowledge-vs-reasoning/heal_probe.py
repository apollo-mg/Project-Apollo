#!/usr/bin/env python3
"""Is the pruned model's confident error NOISE AROUND THE TRUTH or FALLBACK TO PRIOR?

h4rm0n1c's hypothesis: post-REAP errors "land near the right answer" the way TurboQuant's
quantization error does, so a healing pass could pull them back. That is only true if the
information is DEGRADED-but-present. If instead the surviving experts are generating from a
shape prior with no residual pointer to the fact, healing is not denoising -- it is re-learning.

Testable proxy, computed here on the 98 CORRECT->WRONG transitions:

  (a) IS_REAL_ENTITY  -- does the wrong answer appear as the GOLD of some other probe, or as a
      base-model CORRECT answer elsewhere in the set? A wrong answer drawn from the corpus of
      true things is neighbourhood retrieval => residual signal.
  (b) NOVEL           -- the wrong answer appears nowhere. Confabulation from prior.
  (c) NUMERIC_NEAR    -- both gold and response are years/numbers; report |delta|.

Reads the two runs, replays ikp_score.grade, emits the transitions and the proxy tallies.
"""
import json, re, sys, unicodedata
from collections import defaultdict

sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade, norm

BASE = "ikp_glm_base_rep2.jsonl"
REAP = "ikp_glm_reap_rep1.jsonl"
EXCLUDE = {"researcher"}


def load(path):
    out = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("source_type") in EXCLUDE:
                continue
            out[r["id"]] = r
    return out


base, reap = load(BASE), load(REAP)
ids = sorted(set(base) & set(reap))

# --- the universe of TRUE strings this probe set knows about -------------------------------
gold_terms = set()
for r in base.values():
    for a in str(r["gold"]).split(";"):
        a = norm(a)
        if len(a) >= 3:
            gold_terms.add(a)
# plus every short answer the BASE model got right (its own vocabulary of true things)
base_correct_terms = set()
for r in base.values():
    v, _ = grade(r["gold"], r.get("response", ""), 25, r.get("finish_reason"))
    if v == "CORRECT":
        t = norm(r.get("response", ""))
        if 3 <= len(t) <= 60:
            base_correct_terms.add(t)

TRUE_UNIVERSE = gold_terms | base_correct_terms
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")

rows = []
for i in ids:
    b, p = base[i], reap[i]
    vb, _ = grade(b["gold"], b.get("response", ""), 25, b.get("finish_reason"))
    vp, _ = grade(p["gold"], p.get("response", ""), 25, p.get("finish_reason"))
    if not (vb == "CORRECT" and vp == "WRONG"):
        continue
    resp = (p.get("response") or "").strip()
    nresp = norm(resp)

    # (a) does the pruned answer contain a TRUE thing from elsewhere in the corpus?
    borrowed = sorted((t for t in TRUE_UNIVERSE
                       if len(t) >= 4 and re.search(rf"(?<!\w){re.escape(t)}(?!\w)", nresp)),
                      key=len, reverse=True)
    # drop terms that are just the gold's own words leaking in
    gold_n = norm(b["gold"])
    borrowed = [t for t in borrowed if t != gold_n]

    # (c) numeric proximity
    gy, py = YEAR.findall(str(b["gold"])), YEAR.findall(resp)
    delta = abs(int(gy[0]) - int(py[0])) if gy and py else None

    rows.append(dict(id=i, tier=b["tier"], domain=b.get("domain"), q=b["question"],
                     gold=b["gold"], base=(b.get("response") or "").strip()[:70],
                     pruned=resp[:110], borrowed=borrowed[:2], year_delta=delta))

print(f"CORRECT -> WRONG transitions: {len(rows)}\n")

n_borrowed = sum(1 for r in rows if r["borrowed"])
n_year = sum(1 for r in rows if r["year_delta"] is not None)
near_year = [r["year_delta"] for r in rows if r["year_delta"] is not None]

print("=== PROXY TALLY ==========================================================")
print(f"  wrong answer BORROWS a true entity from the corpus : {n_borrowed:3d} / {len(rows)} "
      f"({n_borrowed/len(rows):.0%})   <- residual-signal / neighbourhood retrieval")
print(f"  wrong answer is NOVEL (nothing true in it)         : {len(rows)-n_borrowed:3d} / {len(rows)} "
      f"({(len(rows)-n_borrowed)/len(rows):.0%})   <- confabulation from prior")
if near_year:
    near_year.sort()
    print(f"\n  numeric (year) probes among these                 : {n_year}")
    print(f"  |year delta|: min={near_year[0]} median={near_year[len(near_year)//2]} "
          f"max={near_year[-1]}   within 5y={sum(1 for d in near_year if d<=5)}")

by_domain = defaultdict(int)
for r in rows:
    by_domain[r["domain"]] += 1
print("\n  by domain: " + ", ".join(f"{k}={v}" for k, v in
                                    sorted(by_domain.items(), key=lambda x: -x[1])[:10]))

print("\n=== ALL TRANSITIONS ======================================================")
for r in sorted(rows, key=lambda r: (not r["borrowed"], r["tier"])):
    tag = f"BORROWED:{r['borrowed'][0]}" if r["borrowed"] else "NOVEL"
    if r["year_delta"] is not None:
        tag += f" |dy|={r['year_delta']}"
    print(f"\n[{r['tier']} {r['domain']:<12}] {tag}")
    print(f"  Q     {r['q'][:96]}")
    print(f"  gold  {r['gold'][:70]}")
    print(f"  base  {r['base']}")
    print(f"  REAP  {r['pruned']}")
