#!/usr/bin/env python3
"""Score the --reasoning-budget smoke cells against PREREG_REASONING_BUDGET_SMOKE.md.

"LIVE at budget 0" is defined against each model's OWN budget--1 baseline, never in the
absolute: absent reasoning only means the flag worked if the -1 cell proved the template
emits reasoning at all (gate G-RB0). A model that fails G-RB0 is reported as UNINTERPRETABLE,
not as a pass.

Reasoning *tokens* are not returned separately by the server, only reasoning *chars*; the
bound check therefore uses chars as the primary signal and prints a chars/4 token estimate
clearly labelled as an estimate, never as a measurement.
"""
import json, os, sys

R = os.path.dirname(os.path.abspath(__file__))
CELLS = os.path.join(R, "cells")
MODELS = ["BONSAI", "GEMMA"]
BUDGETS = [("-1", "bm1"), ("0", "b0"), ("1024", "b1024")]


def load(model, suffix):
    p = os.path.join(CELLS, f"{model}_{suffix}.jsonl")
    if not os.path.exists(p):
        return None
    rows = [json.loads(l) for l in open(p) if l.strip()]
    ok = [r for r in rows if "error" not in r]
    if not ok:
        return None
    n = len(ok)
    toks = [r["completion_tokens"] for r in ok if r.get("completion_tokens") is not None]
    return dict(
        n=n,
        with_reason=sum(1 for r in ok if r["has_reasoning"]),
        with_content=sum(1 for r in ok if r["has_content"]),
        mean_rch=sum(r["reasoning_chars"] for r in ok) / n,
        mean_cch=sum(r["content_chars"] for r in ok) / n,
        mean_tok=(sum(toks) / len(toks)) if toks else None,
        caps=sum(1 for r in ok if r.get("finish_reason") == "length"),
        stops=sum(1 for r in ok if r.get("finish_reason") == "stop"),
        errors=len(rows) - n,
    )


D = {m: {b: load(m, s) for b, s in BUDGETS} for m in MODELS}

hdr = (f"{'model':<9}{'budget':>7}{'n':>4}{'w/reason':>10}{'w/content':>11}"
       f"{'mean_rch':>10}{'mean_cch':>10}{'mean_tok':>10}{'cap':>5}{'stop':>6}")
print(hdr); print("-" * len(hdr))
for m in MODELS:
    for b, _ in BUDGETS:
        d = D[m][b]
        if not d:
            print(f"{m:<9}{b:>7}{'  -- not run --':>40}"); continue
        mt = f"{d['mean_tok']:.0f}" if d["mean_tok"] is not None else "n/a"
        print(f"{m:<9}{b:>7}{d['n']:>4}{d['with_reason']:>10}{d['with_content']:>11}"
              f"{d['mean_rch']:>10.0f}{d['mean_cch']:>10.0f}{mt:>10}{d['caps']:>5}{d['stops']:>6}")
print("-" * len(hdr))

print("\n=== GATES ===")
for m in MODELS:
    d = D[m]["-1"]
    if not d:
        print(f"  G-RB0 {m}: NOT RUN"); continue
    ok = d["with_reason"] >= 4
    print(f"  G-RB0 {m}: {d['with_reason']}/{d['n']} carried reasoning at budget -1 -> "
          f"{'PASS — budget cells interpretable' if ok else 'FAIL — model UNINTERPRETABLE, do not score'}")

print("\n=== PREDICTION SCORING (PREREG §Predictions) ===")


def live(m):
    """budget 0 is LIVE iff the -1 gate passed AND reasoning collapses at 0."""
    base, zero = D[m]["-1"], D[m]["0"]
    if not base or not zero:
        return None, "cell missing"
    if base["with_reason"] < 4:
        return None, "G-RB0 failed — uninterpretable"
    if zero["with_reason"] <= 1:
        return True, f"reasoning {base['with_reason']}/{base['n']} -> {zero['with_reason']}/{zero['n']}"
    return False, f"reasoning still present at 0: {zero['with_reason']}/{zero['n']} (INERT)"


for pid, m, conf in [("P-RB1", "GEMMA", 0.75), ("P-RB2", "BONSAI", 0.50)]:
    v, why = live(m)
    verdict = "HELD" if v else ("FALSIFIED" if v is False else "UNSCORED")
    print(f"  {pid}  budget 0 LIVE on {m:<7} (conf {conf}) : {verdict} — {why}")

base, zero = D["BONSAI"]["-1"], D["BONSAI"]["0"]
if base and zero and base["mean_tok"] and zero["mean_tok"]:
    drop = 1 - zero["mean_tok"] / base["mean_tok"]
    print(f"  P-RB3  BONSAI completion_tokens drop >=50% at 0 (conf 0.70) : "
          f"{base['mean_tok']:.0f} -> {zero['mean_tok']:.0f} = {drop:.1%} -> "
          f"{'HELD' if drop >= 0.50 else 'FALSIFIED'}")
else:
    print("  P-RB3  UNSCORED — cell missing")

print("  P-RB4  positive budget (1024) honoured as a BOUND (conf 0.65):")
for m in MODELS:
    b1, bb = D[m]["-1"], D[m]["1024"]
    if not b1 or not bb:
        print(f"         {m:<7}: UNSCORED — cell missing"); continue
    bounded = bb["mean_rch"] < b1["mean_rch"]
    est = bb["mean_rch"] / 4
    print(f"         {m:<7}: mean_reasoning_chars {b1['mean_rch']:.0f} -> {bb['mean_rch']:.0f} "
          f"({'bounded' if bounded else 'NOT bounded'}); ~{est:.0f} est. tokens vs 1024 budget "
          f"[chars/4 ESTIMATE, not a measurement]")
    print(f"                  content recovered: {b1['with_content']}/{b1['n']} -> "
          f"{bb['with_content']}/{bb['n']}  <-- the intervention that matters")

print("\n=== THE ARTICLE QUESTION: does a bounded budget rescue the empties? ===")
for m in MODELS:
    row = []
    for b, _ in BUDGETS:
        d = D[m][b]
        row.append(f"{b}={d['with_content']}/{d['n']}" if d else f"{b}=--")
    print(f"  {m:<8} responses carrying an ANSWER:  " + "   ".join(row))
print("\n  P-RB5 (panel-level) is NOT scoreable here and remains unscored — it needs the full"
      "\n  541-prompt panel at max_tokens=4096, which this leg does not authorise.")
