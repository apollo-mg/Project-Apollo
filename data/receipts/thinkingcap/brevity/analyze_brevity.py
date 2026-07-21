#!/usr/bin/env python3
"""Paired brevity analysis: stock vs ThinkingCap think/answer token counts.
Usage: analyze_brevity.py stock.jsonl tc.jsonl"""
import json
import math
import sys


def load(path):
    rows = {}
    for line in open(path):
        r = json.loads(line)
        if "error" not in r:
            rows[(r["idx"], r["seed"])] = r
    return rows


def sign_test(deltas):
    nz = [d for d in deltas if d != 0]
    if not nz:
        return 0, 0, 1.0
    pos = sum(1 for d in nz if d > 0)
    n = len(nz)
    mu, sd = n / 2, math.sqrt(n) / 2
    z = (pos - mu) / sd if sd else 0.0
    p = math.erfc(abs(z) / math.sqrt(2))
    return pos, n, p


def paired_t(deltas):
    n = len(deltas)
    if n < 3:
        return float("nan"), n
    m = sum(deltas) / n
    var = sum((d - m) ** 2 for d in deltas) / (n - 1)
    if var == 0:
        return float("inf") if m else 0.0, n
    return m / math.sqrt(var / n), n


def med(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


stock, tc = load(sys.argv[1]), load(sys.argv[2])
keys = sorted(set(stock) & set(tc))
print(f"pairs: {len(keys)} (stock rows {len(stock)}, tc rows {len(tc)})")

for field in ("think_tokens", "answer_tokens"):
    s_vals = [stock[k][field] for k in keys]
    t_vals = [tc[k][field] for k in keys]
    # censoring: a pair is suspect if either side hit the length cap
    cens = [k for k in keys
            if stock[k]["finish"] == "length" or tc[k]["finish"] == "length"]
    clean = [k for k in keys if k not in set(cens)]
    d_all = [tc[k][field] - stock[k][field] for k in keys]
    d_cln = [tc[k][field] - stock[k][field] for k in clean]
    logd = [math.log(tc[k][field]) - math.log(stock[k][field])
            for k in clean if tc[k][field] > 0 and stock[k][field] > 0]
    pos, n, p = sign_test(d_cln)
    t, tn = paired_t(logd)
    ratio = math.exp(sum(logd) / len(logd)) if logd else float("nan")
    print(f"\n== {field} ==")
    print(f"  median stock {med(s_vals):.0f}  tc {med(t_vals):.0f}  "
          f"(tc/stock medians = {med(t_vals)/med(s_vals):.3f})")
    print(f"  mean   stock {sum(s_vals)/len(s_vals):.0f}  tc {sum(t_vals)/len(t_vals):.0f}")
    print(f"  censored pairs (either side hit cap): {len(cens)}")
    print(f"  clean pairs: {len(clean)}  tc-longer {pos}/{n} nonzero  sign-p {p:.2e}")
    print(f"  paired t on log-ratio (clean, n={tn}): t={t:.2f}  geo-mean tc/stock = {ratio:.3f}")

no_think_s = sum(1 for k in keys if not stock[k]["has_think"])
no_think_t = sum(1 for k in keys if not tc[k]["has_think"])
print(f"\nno-think rows: stock {no_think_s}, tc {no_think_t}")
lc_s = sum(1 for k in keys if stock[k]["finish"] == "length")
lc_t = sum(1 for k in keys if tc[k]["finish"] == "length")
print(f"length-capped: stock {lc_s}, tc {lc_t}")
