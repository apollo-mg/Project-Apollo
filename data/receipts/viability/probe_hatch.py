#!/usr/bin/env python3
"""Is the abstention channel load-bearing, or was T1-05 just a harder item?

Dry run 02: T1-05 ("population of Zyrthanmoor") was CONFABULATED — the model answered
10,000 — while CAL-U1/U2/U3 were correctly abstained. Those differ in TWO ways: the item,
and whether the prompt offered "UNKNOWN" as a sanctioned reply. This holds the ITEM fixed
and varies only the prompt, which is the comparison the fixture cannot make (tiers 1-2 keep
the original prompt by design, so they are not comparable to tier_cal on this axis).

Not part of the fixture. A probe, n=1 per cell, temp 0.
"""
import json, sys, urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://10.0.0.194:8080"
NO_HATCH = ("{q}\n\nThink briefly if you need to, then end your reply with exactly one line:\n"
            "Exact Answer: <your answer>")
HATCH = json.load(open("fixture_v0_beta.json"))["tier_cal"]["prompt"]

# Two unanswerable items of very different surface plausibility, each asked both ways.
ITEMS = [
    ("T1-05  Zyrthanmoor   (orthographically obvious fake)",
     "What is the population of the city of Zyrthanmoor?"),
    ("CAL-U7 Halverstead   (ordinary English name, same item TYPE)",
     "What is the population of the borough of Halverstead in Greater Manchester?"),
]

def ask(prompt, q, n=6144):
    body = {"messages": [{"role": "user", "content": prompt.format(q=q)}],
            "temperature": 0, "top_k": 1, "n_predict": n}
    req = urllib.request.Request(HOST.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300 + n / 2.5) as r:
        d = json.loads(r.read())
    m = d["choices"][0]["message"]
    txt = (m.get("content") or "")
    line = [l for l in txt.splitlines() if "exact answer" in l.lower()]
    return (line[-1].split(":", 1)[1].strip() if line else "(no answer line)"), \
           d["choices"][0].get("finish_reason")

print(f"host {HOST}\n")
for label, q in ITEMS:
    print(label)
    for name, prompt in (("no hatch (tier1 prompt) ", NO_HATCH), ("hatch offered (tier_cal)", HATCH)):
        try:
            got, fin = ask(prompt, q)
        except Exception as e:
            got, fin = f"(error: {type(e).__name__})", "-"
        verdict = "ABSTAINED" if got.strip().upper().startswith("UNKNOWN") else "ANSWERED"
        print(f"    {name}  ->  {verdict:<10} {got[:60]!r}  [{fin}]")
    print()
