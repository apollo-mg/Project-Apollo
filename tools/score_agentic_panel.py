#!/usr/bin/env python3
"""Score the agentic panel against PREREG_AGENTIC_LADDER.md.

Determinism (P-A0, 15/15 verdicts AND tool paths identical) means the noise floor is zero, so a
single scenario differing between arms is a real difference. Comparisons are therefore PAIRED
per scenario, not aggregate-rate-vs-aggregate-rate.
"""
import json, sys, argparse, collections

SUCCESS  = {"CORRECT", "CLARIFIED"}
DECISION = {"WRONG", "NO-ATTEMPT", "SUSPECT"}
VOID     = {"INFRA", "TOOL-FAIL"}

# scored bpw and mean KLD from the fidelity ladder, for the KLD-vs-task comparison
FID = {
    "P-BASE":  (6.522, 0.002770, "Q6_K anchor"),
    "P-AIQ3S": (3.732, 0.048110, "AD IQ3_S"),
    "P-GIQ2":  (2.476, 0.202243, "GSQ-RCO IQ2_XS"),
    "P-BPQ2":  (2.119, 0.358047, "Bonsai 2 PQ2_0"),
}

ap = argparse.ArgumentParser()
ap.add_argument("runs", nargs="+", help="panel_<ARM>.jsonl files")
a = ap.parse_args()

arms = {}
for p in a.runs:
    arm = p.split("panel_")[-1].replace(".jsonl", "")
    arms[arm] = {json.loads(l)["id"]: json.loads(l) for l in open(p) if l.strip()}

order = [k for k in ("P-BASE", "P-AIQ3S", "P-GIQ2", "P-BPQ2") if k in arms]
if not order:
    order = sorted(arms)

print("=" * 96)
print("AGENTIC PANEL -- Qwen3.8-27B, one corpus, one binary, one world (seed 806c5016)")
print("=" * 96)
print(f"{'arm':<9}{'codec':<18}{'s.bpw':>7}{'mean KLD':>10}  {'OK':>3}{'CLAR':>5}{'WRNG':>5}{'NOAT':>5}{'SUSP':>5}{'VOID':>5}{'success':>9}")
print("-" * 96)
rates = {}
for arm in order:
    rows = arms[arm]
    c = collections.Counter(r["verdict"] for r in rows.values())
    s = sum(c[v] for v in SUCCESS); d = sum(c[v] for v in DECISION); v = sum(c[x] for x in VOID)
    n = len(rows); valid = n - v
    rates[arm] = (s, d, v, n, s / valid if valid else 0)
    bpw, kld, name = FID.get(arm, (0, 0, "?"))
    pct = (s / valid * 100) if valid else 0.0
    print(f"{arm:<9}{name:<18}{bpw:>7.3f}{kld:>10.6f}  {c['CORRECT']:>3}{c['CLARIFIED']:>5}"
          f"{c['WRONG']:>5}{c['NO-ATTEMPT']:>5}{c['SUSPECT']:>5}{v:>5}" + f"{s}/{valid} ({pct:.0f}%)".rjust(9))

if "P-BASE" in rates:
    print("\n" + "=" * 96); print("RETENTION vs the Q6_K anchor"); print("=" * 96)
    b = rates["P-BASE"][4]
    print(f"  anchor success rate: {b*100:.1f}%")
    for arm in order:
        if arm == "P-BASE": continue
        r = rates[arm][4]
        print(f"  {arm:<9} {r*100:5.1f}%  -> retention {r/b*100 if b else 0:5.1f}%   "
              f"(PrismML's own paper reports ~76% agentic retention for Bonsai 2)")

print("\n" + "=" * 96); print("PREDICTIONS"); print("=" * 96)

print("\nP-A1  decision failures monotonic in KLD: BPQ2 >= GIQ2 >= AIQ3S")
seq = [x for x in ("P-BPQ2", "P-GIQ2", "P-AIQ3S") if x in rates]
if len(seq) < 2:
    print("  PENDING")
else:
    vals = [(x, rates[x][1]) for x in seq]
    mono = all(vals[i][1] >= vals[i+1][1] for i in range(len(vals)-1))
    print("  " + "  >=  ".join(f"{k}={v}" for k, v in vals) + f"   -> {'HOLDS' if mono else 'INVERTED'}")

print("\nP-A2  THE TEST: Bonsai's decision-failure excess over GSQ exceeds what KLD predicts")
if "P-BPQ2" in rates and "P-GIQ2" in rates:
    kb, kg = FID["P-BPQ2"][1], FID["P-GIQ2"][1]
    db, dg = rates["P-BPQ2"][1], rates["P-GIQ2"][1]
    kr = kb / kg
    if dg == 0:
        print(f"  GSQ had ZERO decision failures ({db} for Bonsai) -- ratio undefined.")
        print("  P-A2 cannot be scored as a ratio; report the raw counts instead.")
        dr = None
    else:
        dr = db / dg
    print(f"  KLD ratio (Bonsai/GSQ):            {kr:.2f}x")
    print(f"  decision-failure ratio:            {dr:.2f}x   ({db} vs {dg})")
    if dr is None:
        pass
    elif dr > kr:
        print(f"  -> CONFIRMED: task degradation ({dr:.2f}x) OUTRUNS fidelity degradation ({kr:.2f}x)")
    else:
        print(f"  -> FALSIFIED: task degradation ({dr:.2f}x) does NOT outrun fidelity ({kr:.2f}x)")
    print("  NOTE: with 15 scenarios these are small counts; a 1-scenario move changes the ratio a lot.")
else:
    print("  PENDING")

print("\nP-A3  the excess lands in DECISION classes, not VOID")
tv = sum(rates[x][2] for x in order)
print(f"  total VOID across all arms: {tv}")
print(f"  -> {'CONFIRMED' if tv == 0 else 'CHECK: void present, see per-arm table'}")

print("\n" + "=" * 96); print("DISCRIMINATING POWER -- how many scenarios can tell the arms apart?"); print("=" * 96)
ids_all = sorted(set().union(*[set(v) for v in arms.values()]))
uni_pass, uni_fail, disc, mixed_void = [], [], [], []
for i in ids_all:
    vs = [arms[a_][i]["verdict"] for a_ in order if i in arms[a_]]
    if len(vs) < len(order):
        continue
    if all(v in VOID for v in vs):        mixed_void.append(i)
    elif all(v in SUCCESS for v in vs):   uni_pass.append(i)
    elif all(v in DECISION for v in vs):  uni_fail.append(i)
    else:                                 disc.append(i)
n = len(ids_all)
print(f"  scenarios: {n}")
print(f"  ALL arms succeed  : {len(uni_pass):>2}   {', '.join(uni_pass) if uni_pass else '-'}")
print(f"  ALL arms fail     : {len(uni_fail):>2}   {', '.join(uni_fail) if uni_fail else '-'}")
print(f"  DISCRIMINATING    : {len(disc):>2}   {', '.join(disc) if disc else '-'}")
print(f"\n  EFFECTIVE N = {len(disc)} of {n}.")
if len(disc) < n:
    print(f"  {len(uni_pass)+len(uni_fail)} scenarios carry ZERO information about codec choice:")
    print("  a scenario every arm passes, or every arm fails, cannot separate them. A codec")
    print("  ranking rests only on the discriminating subset, and its size is the real power.")
if len(disc) == 0:
    print("  *** NO scenario separates the arms. This corpus cannot rank these codecs. ***")

print("\n" + "=" * 96); print("PAIRED per-scenario (noise floor is zero, so每 difference is real)".replace("每","every ")); print("=" * 96)
ids = sorted(set().union(*[set(v) for v in arms.values()]))
print(f"{'scenario':<24}" + "".join(f"{a_:<12}" for a_ in order))
for i in ids:
    row = f"{i:<24}"
    for a_ in order:
        row += f"{arms[a_].get(i, {}).get('verdict', '-'):<12}"
    vs = {arms[a_].get(i, {}).get("verdict") for a_ in order}
    print(row + ("" if len(vs) == 1 else "  <-- differs"))
