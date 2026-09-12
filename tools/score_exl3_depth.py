#!/usr/bin/env python3
"""Score PREREG_EXL3_DRAFT_DEPTH.md (EXL3 campaign, test 6) from the driver's results.jsonl.

Usage: score_exl3_depth.py data/receipts/exl3-campaign/depth/results.jsonl
"""
import json, statistics, sys

rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
DEPTHS = [0, 1, 2, 3, 5, 7]
ARMS = [a for a in ("X", "Q") if any(r.get("arm") == a and r.get("stage") == "depth" for r in rows)]


def at(arm, k):
    return [r for r in rows if r.get("arm") == arm and r.get("stage") == "depth" and r.get("depth") == k]


def t(r, key):
    return (r.get("timings") or {}).get(key)


def decode(arm, k):
    v = [x for x in (t(r, "predicted_per_second") for r in at(arm, k)) if x]
    return statistics.median(v) if v else None


def acceptance(arm, k):
    rs = at(arm, k)
    n = sum(int(t(r, "draft_n") or 0) for r in rs)
    a = sum(int(t(r, "draft_n_accepted") or 0) for r in rs)
    return (a / n if n else None), n


def gain(arm, k):
    d0, dk = decode(arm, 0), decode(arm, k)
    return dk / d0 if d0 and dk else None


def fmt(x, spec=".2f"):
    return "-" if x is None else format(x, spec)


print("| arm | " + " | ".join(f"depth {k}" for k in DEPTHS) + " |")
print("|---" * (1 + len(DEPTHS)) + "|")
for a in ARMS:
    print(f"| {a} decode t/s | " + " | ".join(fmt(decode(a, k)) for k in DEPTHS) + " |")
    print(f"| {a} gain vs depth 0 | " + " | ".join(fmt(gain(a, k)) for k in DEPTHS) + " |")
    print(f"| {a} acceptance | " + " | ".join(fmt(acceptance(a, k)[0], '.3f') for k in DEPTHS) + " |")
    print(f"| {a} drafted tokens | " + " | ".join(str(acceptance(a, k)[1]) for k in DEPTHS) + " |")


def best(arm):
    cand = [(decode(arm, k), k) for k in DEPTHS if decode(arm, k) is not None]
    return max(cand)[1] if cand else None


print("\n## Predictions\n")


def verdict(ok):
    return "CONFIRMED" if ok else "FALSIFIED"


gate = True
for a in ARMS:
    d1, d7 = acceptance(a, 1)[1], acceptance(a, 7)[1]
    ok = d1 > 0 and d7 >= 2 * d1
    gate = gate and ok
    print(f"- **P-S0** ({a}): {verdict(ok)} (drafted {d1} at depth 1 vs {d7} at depth 7)")
if len(ARMS) < 2:
    gate = False
    print("  - fewer than two arms ran")
if not gate:
    print("  - **VOID: the per-request depth field is inert or an arm is missing.** Everything below is "
          "descriptive; the test needs a server restart per depth.")
bx, bq = best("X"), best("Q")
tag = "" if gate else " [descriptive]"
print(f"- **P-S1**{tag}: " + ("NOT TESTABLE" if bx is None else f"{verdict(bx <= 3)} (EXL3's best depth is {bx})"))
print(f"- **P-S2**{tag}: " + ("NOT TESTABLE" if bq is None else f"{verdict(bq >= 3)} (Q6_K's best depth is {bq})"))
gx = gain("X", bx) if bx is not None else None
print(f"- **P-S3**{tag}: " + ("NOT TESTABLE" if gx is None else
                              f"{verdict(gx < 1.4)} (EXL3's gain at depth {bx} is {gx:.3f}x)"))
pairs = [(k, gain("X", k), gain("Q", k)) for k in DEPTHS if k >= 1 and gain("X", k) and gain("Q", k)]
ok = bool(pairs) and all(x < q for _, x, q in pairs)
print(f"- **P-S4**{tag}: " + (verdict(ok) + " (" + ", ".join(f"d{k}: {x:.2f} vs {q:.2f}" for k, x, q in pairs) + ")"
                              if pairs else "NOT TESTABLE"))

print("\n## Descriptive\n")
for a in ARMS:
    d0 = decode(a, 0)
    n0 = acceptance(a, 0)[1]
    print(f"- {a}: depth 0 decodes {fmt(d0)} t/s with {n0} drafted tokens "
          f"({'drafting is off as assumed' if n0 == 0 else 'drafting did NOT switch off -- see the prereg fallback'})")
