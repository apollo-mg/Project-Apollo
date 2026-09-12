#!/usr/bin/env python3
"""Score PREREG_EXL3_MTP_SWEEP.md (EXL3 campaign, test 4) mechanically from the driver's results.jsonl.

Usage: score_exl3_mtp.py data/receipts/exl3-campaign/mtp/results.jsonl
"""
import json, sys

pp, tg = {}, {}      # arm -> {ubatch: t/s}
for line in open(sys.argv[1]):
    if not line.strip():
        continue
    r = json.loads(line)
    if r.get("stage") != "bench":
        continue
    d = pp if r.get("n_prompt") else tg
    d.setdefault(r["arm"], {})[r["n_ubatch"]] = r["avg_ts"]

UBS = [1, 2, 4, 8, 16]
ARMS = [a for a in ("X", "Q") if a in pp]


def A(arm, m):
    d = pp.get(arm, {})
    return d[m] / d[1] if d.get(m) and d.get(1) else None


def fmt(x, spec=".2f"):
    return "-" if x is None else format(x, spec)


print("| arm | " + " | ".join(f"pp64 ub{u}" for u in UBS) + " | " + " | ".join(f"A({u})" for u in UBS[1:]) + " |")
print("|---" * (1 + len(UBS) + len(UBS) - 1) + "|")
for a in ARMS:
    row = [fmt(pp[a].get(u)) for u in UBS] + [fmt(A(a, u)) for u in UBS[1:]]
    print(f"| {a} | " + " | ".join(row) + " |")
print("\n| arm | " + " | ".join(f"tg8 at ub{u}" for u in UBS) + " | spread |")
print("|---" * (2 + len(UBS)) + "|")
for a in ARMS:
    v = [tg.get(a, {}).get(u) for u in UBS]
    ok = [x for x in v if x]
    spread = (max(ok) - min(ok)) / min(ok) if len(ok) > 1 else None
    print(f"| {a} | " + " | ".join(fmt(x) for x in v) + f" | {fmt(spread, '.1%')} |")

print("\n## Predictions\n")


def verdict(ok):
    return "CONFIRMED" if ok else "FALSIFIED"


spreads = {}
for a in ARMS:
    ok = [x for x in (tg.get(a, {}).get(u) for u in UBS) if x]
    spreads[a] = (max(ok) - min(ok)) / min(ok) if len(ok) > 1 else None
control = all(s is not None and s < 0.10 for s in spreads.values()) and len(ARMS) == 2
print(f"- **P-M0** (control): {verdict(control)} (tg8 spread " +
      ", ".join(f"{a} {fmt(spreads[a], '.1%')}" for a in ARMS) + ")")
if not control:
    print("  - **The control failed, so every result below is DESCRIPTIVE, not a scored prediction.**")
ax4, aq4, ax8, aq8 = A("X", 4), A("Q", 4), A("X", 8), A("Q", 8)
tag = "" if control else " [descriptive]"
print(f"- **P-M1**{tag}: " + ("NOT TESTABLE (no Q)" if aq4 is None else f"{verdict(aq4 >= 2.5)} (A_Q(4) = {aq4:.2f})"))
print(f"- **P-M2**{tag}: " + ("NOT TESTABLE" if None in (ax4, aq4) else
                              f"{verdict(ax4 < aq4)} (A_X(4) = {ax4:.2f} vs A_Q(4) = {aq4:.2f})"))
print(f"- **P-M3**{tag}: " + ("NOT TESTABLE" if ax4 is None else f"{verdict(ax4 < 2.0)} (A_X(4) = {ax4:.2f})"))
print(f"- **P-M4**{tag}: " + ("NOT TESTABLE" if None in (ax8, aq8) else
                              f"{verdict(ax8 < aq8)} (A_X(8) = {ax8:.2f} vs A_Q(8) = {aq8:.2f})"))

print("\n## Descriptive: above the 8-row limit\n")
for a in ARMS:
    v8, v16 = pp[a].get(8), pp[a].get(16)
    if v8 and v16:
        print(f"- {a}: pp64 goes {v8:.2f} -> {v16:.2f} t/s from ub 8 to ub 16 ({v16 / v8:.2f}x), "
              f"where both kernels' small-batch paths end")
