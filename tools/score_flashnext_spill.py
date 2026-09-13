#!/usr/bin/env python3
"""Score PREREG_FLASHNEXT_SPILL_LADDER.md (qwen4exp Stage 4) from flashnext_res/results.jsonl.

Usage: score_flashnext_spill.py <results.jsonl>

The ladder: Flash-Next UD-IQ4_XS on .194, -ncmoe in {2,4,8,16,32,48}, every rung under --numa distribute and
-lv 4. Rung 2 is the baseline -- -ncmoe 0 does not fit (Stage 3 P-S1), so the fit runs through a shifted
origin and no zero-spill figure is reported as measured.

The deliverable is the exchange rate table (MiB freed per tok/s lost). P-L1 is the falsifiable one: decode
time per token linear in the spilled-layer count, marginal cost 0.5-1.5 ms/layer/token.
"""
import json, sys
from statistics import median

RUNGS = (2, 4, 8, 16, 32, 48)
HEAD_LEN = 500          # the length the residency receipt's ranking table quotes
S3_X4_TPS = 21.28       # Stage 3, same flags, no numa pin -- P-L4's reference
SLOPE_LO, SLOPE_HI = 0.5, 1.5      # ms per spilled layer per token
TOP_LO, TOP_HI = 8.0, 15.0         # tok/s at rung 48
FLAT_TOL = 0.15                    # P-L0: MiB freed per layer constant within +-15%


def verdict(ok):
    return "CONFIRMED" if ok else "FALSIFIED"


def lstsq(xs, ys):
    """Least squares y = a + b*x, plus R^2. Returns (a, b, r2)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    return a, b, (1 - ss_res / ss_tot if ss_tot else float("nan"))


rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
arms = {}
for r in rows:
    a = r.get("arm", "")
    if not a.startswith("L-"):
        continue
    d = arms.setdefault(a, {"n": int(a.split("-")[1]), "req": {}, "load": None, "done": None})
    if r.get("stage") == "load" and r.get("ok"):
        d["load"] = r
    elif r.get("stage") == "req":
        d["req"].setdefault(r["len"], []).append(r)
    elif r.get("stage") == "arm_done":
        d["done"] = r

have = sorted((d for d in arms.values() if d["done"] and d["load"]), key=lambda d: d["n"])
if not have:
    print("NOT RUN: no completed ladder rungs in this file")
    sys.exit(0)
missing = [n for n in RUNGS if n not in {d["n"] for d in have}]
if missing:
    print(f"**Partial ladder — rungs {missing} did not complete.** Scored over the rungs that did "
          f"(the prereg's wall-clock rule).\n")


def tps(d, length, key):
    v = [r[key] for r in d["req"].get(length, []) if r.get(key)]
    return median(v) if v else None


print("## The ladder\n")
print("| rung | `-ncmoe` | GPU MiB after load | decode 500 / 1800 / 3600 | prefill 500 / 1800 / 3600 |")
print("|---|---|---|---|---|")
for d in have:
    g = sum(d["load"]["gpu_after_load"])
    dec = " / ".join(f"{tps(d, L, 'tg_tps') or float('nan'):.2f}" for L in (500, 1800, 3600))
    pre = " / ".join(f"{tps(d, L, 'pp_tps') or float('nan'):.1f}" for L in (500, 1800, 3600))
    print(f"| L-{d['n']:02d} | {d['n']} | **{g:,}** | {dec} | {pre} |")

base = have[0]
g0, t0 = sum(base["load"]["gpu_after_load"]), tps(base, HEAD_LEN, "tg_tps")

print(f"\n## Exchange rate — what one spilled layer buys, against rung {base['n']} at {t0:.2f} tok/s\n")
print("| rung | layers spilled vs base | MiB freed | MiB / layer | tok/s lost | **MiB freed per tok/s lost** |")
print("|---|---|---|---|---|---|")
per_layer = []
for d in have[1:]:
    dn, freed = d["n"] - base["n"], g0 - sum(d["load"]["gpu_after_load"])
    lost = t0 - tps(d, HEAD_LEN, "tg_tps")
    per_layer.append(freed / dn)
    rate = f"**{freed / lost:,.0f}**" if lost > 0 else "— *(no loss)*"
    print(f"| L-{d['n']:02d} | {dn} | {freed:,} | {freed / dn:,.0f} | {lost:+.2f} | {rate} |")

print("\n## Predictions\n")

# P-L0 -- MiB freed per spilled layer constant across rungs
if per_layer:
    mean_pl = sum(per_layer) / len(per_layer)
    spread = max(abs(p - mean_pl) for p in per_layer) / mean_pl if mean_pl else float("inf")
    print(f"- **P-L0** MiB freed per spilled layer constant within ±{FLAT_TOL:.0%}: "
          f"{verdict(spread <= FLAT_TOL)} — mean {mean_pl:,.0f} MiB/layer, worst deviation {spread:.1%} "
          f"(range {min(per_layer):,.0f}–{max(per_layer):,.0f})")

# P-L1 -- decode time per token linear in ncmoe
xs = [d["n"] for d in have]
ys = [1000.0 / tps(d, HEAD_LEN, "tg_tps") for d in have]      # ms per token
a, b, r2 = lstsq(xs, ys)
print(f"- **P-L1** decode ms/token linear in `-ncmoe`, marginal {SLOPE_LO}–{SLOPE_HI} ms/layer: "
      f"{verdict(SLOPE_LO <= b <= SLOPE_HI)} — **{b:.3f} ms per spilled layer**, "
      f"intercept {a:.1f} ms, **R² = {r2:.4f}**")
print(f"  - the fit is the test of the campaign's cost model; R² is reported so a *linear-but-wrong-slope* "
      f"result reads differently from a *not-linear* one")

# P-L2 -- decode at the top rung
top = [d for d in have if d["n"] == 48]
if top:
    t48 = tps(top[0], HEAD_LEN, "tg_tps")
    print(f"- **P-L2** decode at rung 48 in {TOP_LO}–{TOP_HI} tok/s: {verdict(TOP_LO <= t48 <= TOP_HI)} "
          f"— **{t48:.2f} tok/s** with every layer's experts on the host")
else:
    print("- **P-L2** decode at rung 48: **NOT RUN** — the top rung did not complete")

# P-L3 -- prefill degrades proportionally less than decode
if top:
    p0, p48 = tps(base, HEAD_LEN, "pp_tps"), tps(top[0], HEAD_LEN, "pp_tps")
    d_dec, d_pre = 1 - t48 / t0, 1 - p48 / p0
    print(f"- **P-L3** prefill's fractional slowdown < decode's: {verdict(d_pre < d_dec)} — "
          f"prefill {p0:.1f} → {p48:.1f} ({d_pre:+.1%}), decode {t0:.2f} → {t48:.2f} ({d_dec:+.1%})")
else:
    print("- **P-L3** prefill vs decode slowdown: **NOT RUN** — needs rung 48")

# P-L4 -- the numa control against S3-X4
if base["n"] == 2:
    off = t0 / S3_X4_TPS - 1
    print(f"- **P-L4** rung 2 under `--numa distribute` within ±10% of S3-X4's {S3_X4_TPS} tok/s: "
          f"{verdict(abs(off) <= 0.10)} — {t0:.2f} tok/s, **{off:+.1%}**")
else:
    print(f"- **P-L4** the numa control: **NOT RUN** — rung 2 did not complete (base is rung {base['n']})")

print(f"\n*Baseline is rung {base['n']}, not zero spill: `-ncmoe 0` does not fit on IQ4_XS (Stage 3 P-S1, card 0 "
      f"at 15,515 of 16,384 MiB). The intercept above is an extrapolation through a shifted origin, not a "
      f"measured zero-spill figure.*")
