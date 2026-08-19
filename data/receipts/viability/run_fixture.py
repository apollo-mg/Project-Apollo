#!/usr/bin/env python3
"""Run the Apollo viability fixture against a llama-server endpoint.

Tier 1 is a GATE: any failure means the stack is broken, not the model.
Tier 2 is a GATE on the model/quant/sampling being sane.
Reports per-tier pass/fail plus the structural outcome of each item.
"""
import argparse, json, os, re, sys, urllib.request

PROMPT = ("{q}\n\nThink briefly if you need to, then end your reply with exactly one line:\n"
          "Exact Answer: <your answer>")
ANS = re.compile(r"Exact Answer\s*:\s*(.+?)(?:\n|$)", re.I | re.S)

def norm(s):
    s = (s or "").strip().lower().rstrip(".")
    s = re.sub(r"[\s,]+", "", s)
    return s

def ask(host, q, n_predict=512, timeout=300):
    body = {"messages": [{"role": "user", "content": PROMPT.format(q=q)}],
            "temperature": 0, "top_k": 1, "n_predict": n_predict}
    req = urllib.request.Request(host.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    m = d["choices"][0]["message"]
    fin = d["choices"][0].get("finish_reason", "")
    return (m.get("content") or ""), (m.get("reasoning_content") or ""), fin

def run_tier(host, tier, label):
    print(f"\n=== {label}: {tier['purpose'][:70]}...")
    print(f"    gate: {tier['gate']}")
    ok = 0
    for it in tier["items"]:
        content, reasoning, fin = ask(host, it["q"])
        # B2 rule: reasoning is admissible only when the response actually finished
        text = content + ("\n" + reasoning if fin != "length" else "")
        m = ANS.search(text)
        got = m.group(1).strip() if m else ""
        gold = it["gold"]
        if gold == "UNKNOWN":
            hit = any(w in norm(got) for w in ("unknown", "doesnotexist", "nosuch",
                                               "fictional", "notreal", "cannot", "noinfo"))
        else:
            hit = norm(got) == norm(gold)
        ok += hit
        status = "PASS" if hit else ("NO-ANSWER" if not got else "FAIL")
        if fin == "length": status += " (truncated)"
        print(f"    {it['id']}  {status:<20} got={got[:34]!r:<38} want={gold!r}")
    print(f"    -> {ok}/{len(tier['items'])}")
    return ok, len(tier["items"])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8080")
    ap.add_argument("--fixture", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                      "fixture_v0_beta.json"))
    ap.add_argument("--tier", choices=["1", "2", "both"], default="both")
    a = ap.parse_args()
    fx = json.load(open(a.fixture))
    res = {}
    if a.tier in ("1", "both"): res["t1"] = run_tier(a.host, fx["tier1"], "TIER 1 (plumbing)")
    if a.tier in ("2", "both"): res["t2"] = run_tier(a.host, fx["tier2"], "TIER 2 (model sanity)")
    print("\n" + "="*70)
    if "t1" in res:
        o, n = res["t1"]; print(f"TIER 1 {'PASS' if o == n else 'FAIL'}  ({o}/{n}, gate {n}/{n})"
                                + ("" if o == n else "   <-- STACK IS BROKEN, stop here"))
    if "t2" in res:
        o, n = res["t2"]; print(f"TIER 2 {'PASS' if o >= 6 else 'FAIL'}  ({o}/{n}, gate >=6/{n})")
