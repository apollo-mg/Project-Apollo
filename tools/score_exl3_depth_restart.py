#!/usr/bin/env python3
"""Score PREREG_EXL3_DRAFT_DEPTH.md Amendment 3 (EXL3 campaign, test 6 redone).

Usage: score_exl3_depth_restart.py data/receipts/exl3-campaign/depth2/results.jsonl
"""
import json, statistics, sys

BASE = {"X": 11.22, "Q": 13.18}      # test 1's MTP-off greedy figures, same node/binary/flags/prompt
D7 = {"X": 8.72, "Q": 14.44}          # attempt 1's depth-7 point (RESULT_EXL3_DEPTH.md)
DEPTHS = [1, 2, 3, 5]

rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
ARMS = [a for a in ("X", "Q") if any(r.get("arm") == a and r.get("stage") == "depth" for r in rows)]


def at(arm, k):
    return [r for r in rows if r.get("arm") == arm and r.get("stage") == "depth" and r.get("depth") == k]


def t(r, key):
    return (r.get("timings") or {}).get(key)


def decode(arm, k):
    v = [x for x in (t(r, "predicted_per_second") for r in at(arm, k)) if x]
    return statistics.median(v) if v else None


def drafted_per_token(arm, k):
    rs = at(arm, k)
    d = sum(int(t(r, "draft_n") or 0) for r in rs)
    n = sum(int(t(r, "predicted_n") or 0) for r in rs)
    return d / n if n else None


def gain(arm, k):
    d = decode(arm, k)
    return d / BASE[arm] if d else None


def fmt(x, spec=".2f"):
    return "-" if x is None else format(x, spec)


print("| arm | MTP off | " + " | ".join(f"depth {k}" for k in DEPTHS) + " | depth 7 |")
print("|---" * (3 + len(DEPTHS)) + "|")
for a in ARMS:
    print(f"| {a} decode t/s | {BASE[a]:.2f} | " + " | ".join(fmt(decode(a, k)) for k in DEPTHS) +
          f" | {D7[a]:.2f} |")
    print(f"| {a} gain | 1.00 | " + " | ".join(fmt(gain(a, k)) for k in DEPTHS) +
          f" | {D7[a] / BASE[a]:.2f} |")
    print(f"| {a} drafted/token | - | " + " | ".join(fmt(drafted_per_token(a, k)) for k in DEPTHS) + " | - |")


def best(arm):
    cand = [(decode(arm, k), k) for k in DEPTHS if decode(arm, k) is not None]
    return max(cand)[1] if cand else None


def verdict(ok):
    return "CONFIRMED" if ok else "FALSIFIED"


print("\n## Predictions\n")
gate = True
for a in ARMS:
    d1, d5 = drafted_per_token(a, 1), drafted_per_token(a, 5)
    ok = bool(d1) and bool(d5) and d5 >= 1.5 * d1
    gate = gate and ok
    print(f"- **P-S5** ({a}): {verdict(ok)} (drafted per token {fmt(d1)} at depth 1 vs {fmt(d5)} at depth 5)")
if not gate:
    print("  - **VOID: depth still does not reach the model.** Everything below is descriptive.")
tag = "" if gate else " [descriptive]"
bx, bq = best("X"), best("Q")
print(f"- **P-S6**{tag}: " + ("NOT TESTABLE" if bx is None else f"{verdict(bx <= 3)} (EXL3's best depth is {bx})"))
print(f"- **P-S7**{tag}: " + ("NOT TESTABLE" if bq is None else f"{verdict(bq >= 3)} (Q6_K's best depth is {bq})"))
gx = gain("X", bx) if bx else None
print(f"- **P-S8**{tag}: " + ("NOT TESTABLE" if gx is None else
                              f"{verdict(gx < 1.4)} (EXL3's gain at depth {bx} is {gx:.3f}x)"))
pairs = [(k, gain("X", k), gain("Q", k)) for k in DEPTHS if gain("X", k) and gain("Q", k)]
print(f"- **P-S9**{tag}: " + (f"{verdict(all(x < q for _, x, q in pairs))} (" +
                              ", ".join(f"d{k}: {x:.2f} vs {q:.2f}" for k, x, q in pairs) + ")"
                              if pairs else "NOT TESTABLE"))

print("\n## The deployment setting\n")
for a in ARMS:
    b = best(a)
    if b is not None:
        print(f"- **{a}**: best `--draft-max {b}` at {fmt(decode(a, b))} t/s ({fmt(gain(a, b))}x over MTP off)")
