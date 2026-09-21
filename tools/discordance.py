#!/usr/bin/env python3
"""Achieved discordance and McNemar sizing for paired tier-CAL runs.

A1_MEASUREMENT_CORPUS_SPEC.md requires every comparison to *report the achieved
discordant count* rather than assume power.  Nothing computed it.  This does.

Two roles:

  * post-hoc  -- given two arms' JSONL, print the 2x2, the achieved discordant
                 count b+c, and whether it clears the >=10 floor below which the
                 chi2 approximation stops working (hle-mini/POWER.md).
  * sizing    -- given the observed discordance RATE, print how many items per
                 arm are needed at each psi in A1's table.

psi is the ALTERNATIVE HYPOTHESIS -- the smallest directional imbalance you want
power against -- not a quantity to estimate from the pilot and feed back in.
Only the discordance rate comes from data.

Usage:
  discordance.py --a run_a_rep*.jsonl --b run_b_rep*.jsonl [--label-a X --label-b Y]
  discordance.py --size 0.125
"""
import argparse
import glob
import json
import math
import sys
from collections import Counter, defaultdict

# pass criterion per arm: everything else (ANSWERED-WRONG, NO-STOP, ...) is a fail
PASS = {"answerable": {"ANSWERED-CORRECT"}, "unanswerable": {"ABSTAINED"}}

Z_ALPHA = 1.959964   # two-sided 0.05
Z_BETA = 0.8416212   # 80% power
MIN_DISCORDANT = 10  # POWER.md: below this the chi2 approximation stops working


def n_discordant(psi, z_alpha=Z_ALPHA, z_beta=Z_BETA):
    """Discordant pairs needed to detect an imbalance psi. Reproduces A1's table."""
    if psi <= 0.5:
        return float("inf")
    return (z_alpha / 2 + z_beta * math.sqrt(psi * (1 - psi))) ** 2 / (psi - 0.5) ** 2


def n_items(psi, rate):
    """Items per arm to harvest that many discordant pairs at a given rate."""
    if rate <= 0:
        return float("inf")
    # ceil at the END, matching how A1's own table was computed -- ceiling the
    # discordant count first shifts three of its cells by a few items.
    return math.ceil(n_discordant(psi) / rate)


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def clopper_pearson(k, n, alpha=0.05):
    """Exact binomial interval, by bisection -- no scipy, so this runs anywhere."""
    if n == 0:
        return (0.0, 1.0)

    def solve(pred):
        """pred is True below the root and False above it; returns the root."""
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if pred(mid):
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    # lower: P(X >= k) rises with p; find where it reaches alpha/2
    low = 0.0 if k == 0 else solve(lambda p: 1 - binom_cdf(k - 1, n, p) <= alpha / 2)
    # upper: P(X <= k) falls with p; find where it drops to alpha/2
    high = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p) > alpha / 2)
    return (low, high)


def load(paths):
    """-> {rep_index: {item_id: record}}, one rep per file, files in sorted order."""
    reps = {}
    for r, path in enumerate(sorted(paths)):
        recs = {}
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    recs[d["id"]] = d
        reps[r] = recs
    return reps


def passed(rec):
    arm = rec["arm"]
    if arm not in PASS:
        raise SystemExit(f"unknown arm {arm!r} on {rec['id']} -- extend PASS")
    return rec["status"] in PASS[arm]


def two_by_two(A, B, ids, arm, collapse):
    """collapse=False: one pair per (item, rep). True: majority vote over reps."""
    a = b = c = d = 0
    discordant_items = Counter()
    if collapse:
        for i in ids:
            pa = sum(passed(A[r][i]) for r in A) * 2 >= len(A)
            pb = sum(passed(B[r][i]) for r in B) * 2 >= len(B)
            a, b, c, d = (a + (pa and pb), b + (pa and not pb),
                          c + (pb and not pa), d + (not pa and not pb))
            if pa != pb:
                discordant_items[i] += 1
    else:
        for r in A:
            for i in ids:
                pa, pb = passed(A[r][i]), passed(B[r][i])
                a, b, c, d = (a + (pa and pb), b + (pa and not pb),
                              c + (pb and not pa), d + (not pa and not pb))
                if pa != pb:
                    discordant_items[i] += 1
    return a, b, c, d, discordant_items


def report_pair(A, B, label_a, label_b):
    ids = sorted(set(A[0]) & set(B[0]))
    missing = (set(A[0]) | set(B[0])) - set(ids)
    if missing:
        print(f"  WARNING: {len(missing)} item(s) not in both arms, dropped: {sorted(missing)}")
    by_arm = defaultdict(list)
    for i in ids:
        by_arm[A[0][i]["arm"]].append(i)

    print(f"\n=== {label_a}  vs  {label_b} ===")
    print(f"    {len(ids)} items, {len(A)} reps each\n")
    for arm, arm_ids in sorted(by_arm.items()):
        for collapse, unit in ((False, "observation"), (True, "item (majority)")):
            a, b, c, d, items = two_by_two(A, B, arm_ids, arm, collapse)
            n = a + b + c + d
            disc = b + c
            rate = disc / n if n else 0.0
            lo, hi = clopper_pearson(disc, n)
            flag = "" if disc >= MIN_DISCORDANT else f"  << under the {MIN_DISCORDANT}-pair floor"
            print(f"  {arm:12} [{unit:15}] n={n:>3}  both+={a:>3} b={b:>2} c={c:>2} both-={d:>2}"
                  f"   b+c={disc:>2}  rate={rate:6.1%}  95% CI [{lo:.1%}, {hi:.1%}]{flag}")
        if items:
            spread = ", ".join(f"{k}x{v}" for k, v in sorted(items.items()))
            print(f"  {'':12} discordance carried by {len(items)}/{len(arm_ids)} items: {spread}")
            print(f"  {'':12} the other {len(arm_ids) - len(items)} contributed nothing at any n")
        print()


def report_sizing(rates):
    psis = (0.60, 0.65, 0.70, 0.75, 0.80, 0.90)
    print("\nItems PER ARM needed, 80% power, alpha=0.05")
    print("psi is the alternative hypothesis -- the imbalance you want to detect.\n")
    head = "  rate  " + "".join(f"  psi={p:<5.2f}" for p in psis)
    print(head)
    print("  " + "-" * (len(head) - 2))
    for rate in rates:
        row = f"  {rate:5.1%} "
        for p in psis:
            need = n_items(p, rate)
            floor = math.ceil(MIN_DISCORDANT / rate)
            mark = "*" if need < floor else " "
            row += f"  {max(need, floor):>7.0f}{mark}"
        print(row)
    print("\n  * the formula asks for fewer than 10 discordant pairs; the printed figure is")
    print("    the 10-pair floor instead (POWER.md -- below it the chi2 approximation fails).")
    print("\n  discordant pairs required: " + ", ".join(f"psi={p}: {math.ceil(n_discordant(p))}" for p in psis))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", nargs="+", help="arm A JSONL (one file per rep)")
    ap.add_argument("--b", nargs="+", help="arm B JSONL (one file per rep)")
    ap.add_argument("--label-a", default="arm A")
    ap.add_argument("--label-b", default="arm B")
    ap.add_argument("--size", type=float, nargs="*", metavar="RATE",
                    help="print the sizing table at these discordance rates")
    args = ap.parse_args()

    if args.a and args.b:
        A, B = load(args.a), load(args.b)
        if len(A) != len(B):
            sys.exit(f"rep count differs: {len(A)} vs {len(B)} -- pairing would be wrong")
        report_pair(A, B, args.label_a, args.label_b)
    if args.size is not None:
        report_sizing(args.size or [0.05, 0.10, 0.125, 0.15, 0.20, 0.30, 0.40, 0.50])
    if not args.a and args.size is None:
        ap.print_help()


if __name__ == "__main__":
    main()
