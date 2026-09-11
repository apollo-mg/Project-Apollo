#!/usr/bin/env python3
"""DESCRIPTIVE ONLY, not pre-registered: rater-level checks on the blind pelican judging.

1. Pair similarity -- are any of the 75 pairs the same picture? Pixel differences between the two
   renders of every pair (composited onto white, exactly as the pages show them).
2. Who agrees with whom -- decisive first-drawing pairs (same rule as P-B6) and Spearman rank
   correlation of the ten first-drawing win rates, for every pair of raters.
3. Side preference -- how often each rater picked the LEFT drawing among decisive picks, with an exact
   two-sided binomial test. The share page flips sides per rater; its rule is replayed from the seed.
"""
import math, statistics, sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_blind as S  # noqa: E402

SRC = S.ROOT / "data/receipts/svgbench-ladder"


def pixels(code):
    im = Image.open(SRC / S.DRAW[code]["png"]).convert("RGBA")
    flat = Image.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, 255)), im).convert("RGB")
    return np.asarray(flat).astype(np.int16)


def spearman(a, b):
    xs, ys = [a[c] for c in S.FIRST], [b[c] for c in S.FIRST]
    rank = lambda v: [sorted(v).index(x) + (sorted(v).count(x) - 1) / 2 for x in v]
    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((p - mx) * (q - my) for p, q in zip(rx, ry))
    return num / (math.sqrt(sum((p - mx) ** 2 for p in rx) * sum((q - my) ** 2 for q in ry)) or 1)


def binom_two_sided(k, n):
    pk = [math.comb(n, j) / 2 ** n for j in range(n + 1)]
    return min(1.0, sum(p for p in pk if p <= pk[k] * (1 + 1e-9)))


def main():
    Jm, _, _ = S.load_mark(S.D / "picks_mark")
    raters = {"Mark": (Jm, None)}
    for f in sorted((S.D / "raters").glob("*_export.txt")):
        J, _, _, seed = S.load_export(f)
        raters[f.stem.replace("_export", "")] = (J, seed)

    print("1. pair similarity (fraction of pixels that differ between the two renders)")
    px = {c: pixels(c) for c in S.DRAW}
    rows = sorted(((np.abs(px[p["pair"][0]] - px[p["pair"][1]]).any(axis=2).mean(), pid, p)
                   for pid, p in S.PAIRS.items()), key=lambda r: r[0])
    print(f"   pixel-identical pairs: {sum(r[0] == 0 for r in rows)} of {len(rows)}")
    for frac, pid, p in rows[:6]:
        lab = S.label(p["child"]) if p["kind"] == "revision" else p["kind"]
        print(f"   {pid} {p['kind']:8s} {frac * 100:5.2f}% of pixels differ  {lab}")

    print("2. who agrees with whom (decisive first-drawing pairs | Spearman over the 10 drawings)")
    V = {k: S.first_values(J) for k, (J, _) in raters.items()}
    W = {k: S.win_rates(v) for k, v in V.items()}
    names = list(raters)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            same, n = S.agreement(V[a], V[b])
            print(f"   {a:4s} vs {b:4s}: agree {same}/{n} = {same / n:.2f} | rho {spearman(W[a], W[b]):+.2f}")

    print("3. side preference (LEFT picks among decisive picks)")
    for name, (J, seed) in raters.items():
        if seed is None:   # Mark's page stored the left code with each pick
            d = [(w, L) for pid, (w, f, L) in J.items() if w not in (None, "=") and not f]
        else:
            d = [(w, S.left_code(pid, seed)) for pid, (w, f, _) in J.items() if w != "=" and not f and pid in S.PAIRS]
        k = sum(w == L for w, L in d)
        print(f"   {name:4s}: left in {k}/{len(d)}, exact two-sided binomial p = {binom_two_sided(k, len(d)):.3f}")


if __name__ == "__main__":
    main()
