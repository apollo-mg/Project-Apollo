#!/usr/bin/env python3
"""Does xhigh earn its cost in a REVIEW role?

tier_cal showed xhigh fabricating on questions with no referent, at 5.85x medium's cost and
with verdicts unstable across seeds. Mark's hypothesis: that failure mode does not transfer to
review, because a critique is checkable against the artifact in front of it — so xhigh's
"validate key assumptions, consider plausible alternatives" becomes a job description instead
of a liability.

Scored on PRECISION and RECALL, not accuracy:
  recall    = real defects found        (RD-* items)
  precision = claims that are not made up (CC-* items are the only way to measure this)

The controls are the point. Without code where the correct answer is "nothing is wrong",
an invented-defect rate cannot be measured at all.
"""
import json, os, sys, urllib.request, collections

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://10.0.0.194:8080"
FX = json.load(open("fixture_review_v0.json"))
SEEDS = [3001, 3002, 3003]

PROMPT = """Review this Python function for defects.

Report ONLY defects you can point to in this code. If the code is correct, say so — reporting
a defect that is not there is worse than reporting none.

```python
{code}
```

Reply with ONLY a JSON object:
{{"defects": [{{"summary": "<one sentence>", "evidence": "<the line or construct>"}}]}}
An empty list means you found nothing wrong."""

def last_schema_object(text):
    """Scan for balanced {...} spans and return the LAST one that parses AND carries the
    expected key. txt.find('{')..txt.rfind('}') spanned the entire reasoning trace — the bug
    that corrupted this probe's xhigh arm and the hard probe before it."""
    best, depth, start, in_str, esc = None, 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:                      # braces inside string VALUES are not structure —
            if esc: esc = False         # the exact defect the model reported in run 1, which
            elif ch == "\\": esc = True # I then reproduced in the scorer that reads its report
            elif ch == '"': in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0: start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                try:
                    o = json.loads(text[start:i+1])
                    if isinstance(o, dict) and "defects" in o: best = o
                except Exception:
                    pass
    return best

def ask(code, effort, seed):
    body = {"messages": [{"role": "user", "content": PROMPT.format(code=code)}],
            "n_predict": 6144, "temperature": 1.0, "top_p": 0.95, "top_k": 20,
            "seed": seed, "chat_template_kwargs": {"reasoning_effort": effort}}
    req = urllib.request.Request(HOST.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2800) as r:
        d = json.loads(r.read())
    m = d["choices"][0]["message"]
    txt = (m.get("content") or "") or (m.get("reasoning_content") or "")
    fin = d["choices"][0].get("finish_reason")
    obj = last_schema_object(m.get("content") or "") 
    if obj is None and fin != "length":
        obj = last_schema_object(m.get("reasoning_content") or "")
    return (obj or {}).get("defects", []), fin, len(txt)

def hit(defects, hints):
    """Did any reported defect name the known one? Keyword match on the item's own hint set."""
    blob = " ".join((d.get("summary","") + " " + d.get("evidence","")).lower()
                    for d in defects if isinstance(d, dict))
    return sum(1 for h in hints if h.lower() in blob) >= 2

out = []
SINK = open("review_results.jsonl", "a", encoding="utf-8")

def persist(row):
    """Append + flush + fsync per item. A run that dies loses at most the item in flight —
    power cut, OOM, harness kill, client timeout, stray pkill. All five happened today."""
    SINK.write(json.dumps(row, ensure_ascii=False) + "\n")
    SINK.flush()
    os.fsync(SINK.fileno())

for effort in ("medium", "xhigh"):
    print(f"\n######## effort={effort}")
    for it in FX["items"]:
        row = []
        for s in SEEDS:
            try:
                ds, fin, n = ask(it["code"], effort, s)
            except Exception as e:
                row.append(("ERR", 0, 0)); continue
            if it["defect"]:
                row.append(("FOUND" if hit(ds, it["hint"]) else "missed", len(ds), n))
            else:
                row.append(("clean" if not ds else f"INVENTED×{len(ds)}", len(ds), n))
            rec = dict(effort=effort, id=it["id"], seed=s, is_defect=bool(it["defect"]),
                       verdict=row[-1][0], n_claims=len(ds), chars=n, defects=ds)
            out.append(rec); persist(rec)
        kind = "DEFECT " if it["defect"] else "control"
        print(f"  {it['id']:<6} {kind} " + "  ".join(f"{v:<12}" for v,_,_ in row), flush=True)

print("\n=== SCORES ===")
for effort in ("medium", "xhigh"):
    rows = [r for r in out if r["effort"] == effort]
    rd = [r for r in rows if r["is_defect"]]; cc = [r for r in rows if not r["is_defect"]]
    found = sum(1 for r in rd if r["verdict"] == "FOUND")
    inv = sum(r["n_claims"] for r in cc)
    print(f"  {effort:<7} planted-defect recall {found}/{len(rd)}   claims on controls: {inv}"
          f"   mean chars {sum(r['chars'] for r in rows)//max(len(rows),1):,}")
