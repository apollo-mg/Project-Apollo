#!/usr/bin/env python3
"""How much of the ladder's pre-registered verdicts do the scorer artifacts carry?

Not a re-grade: score_ladder.py's verdicts stand as the pre-registered result. This recomputes P-L2
and P-L3 under the two obvious handlings of the reps RUN_NOTES.md classifies as scorer artifacts --
counted at the scorer's maximum (as drawn), and excluded -- plus one variant of the unregistered
convergence rule. Neither handling was pre-specified, so a verdict that flips between them is decided
by an unregistered choice, not by the data. The classifications are judgement calls made from renders;
they are listed here verbatim so every counterfactual is explicit and re-checkable.

The last section is EXPLORATORY (explore_ladder.py's measure), not pre-registered.
"""
import math, statistics, sys
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
sys.path.insert(0, str(ROOT / "tools/svgbench"))
import score_ladder as S    # noqa: E402
import explore_ladder as E  # noqa: E402

# RUN_NOTES.md. Artifact calls committed in 5ebbec7 (20:51:55, before any rep-3 data);
# the REAL call and the written rule in 8d73b91 (21:06:05, after rep 3's first drawing, a ceiling rep).
ARTIFACT = {("UD-Q2_K_XL", 2), ("UD-IQ2_M", 2)}
REAL = {("UD-IQ4_XS", 2)}


def as_drawn(r, L):
    """An artifact rep counted as a ceiling first drawing: converged at p1."""
    if (r["quant"], r["rep"]) not in ARTIFACT:
        return r
    return {**r, "p1": r["max"], "ceiling": True, "conv": 1,
            "ttc": L[(r["quant"], r["rep"], "p1")].get("tokens") or 0}


def via_intent(r, L):
    """score_ladder converges along the goal path only; also accept a maximum reached by intent2."""
    i2 = L.get((r["quant"], r["rep"], "intent2"))
    if r["conv"] is not None or not i2 or i2.get("score") is None or i2.get("score") != i2.get("max"):
        return r
    return {**r, "conv": 2,
            "ttc": (L[(r["quant"], r["rep"], "p1")].get("tokens") or 0) + (i2.get("tokens") or 0)}


def verdicts(R):
    q2, q4 = [r for r in R if r["quant"] in S.Q2], [r for r in R if r["quant"] in S.Q4]
    p2, p4 = S.mean([r["p1"] for r in q2]), S.mean([r["p1"] for r in q4])
    t2, t4 = statistics.median([r["ttc"] for r in q2]), statistics.median([r["ttc"] for r in q4])
    return (f"n={len(q2)}v{len(q4)}  P-L2 mean p1 Q2 {p2:.2f} vs Q4 {p4:.2f} -> "
            f"{'CONFIRMED' if p2 < p4 else 'FALSIFIED'}   |   P-L3 median ttc Q2 {S.f(t2, 0)} vs Q4 "
            f"{S.f(t4, 0)} -> {'CONFIRMED' if t2 > t4 else 'FALSIFIED'}")


def main():
    L = S.latest()
    R = S.rows(L)
    print("as pre-registered (raw):         ", verdicts(R))
    print("artifact reps counted as drawn:  ", verdicts([as_drawn(r, L) for r in R]))
    print("artifact reps excluded:          ", verdicts([r for r in R if (r["quant"], r["rep"]) not in ARTIFACT]))
    print("raw, intent2 may also converge:  ", verdicts([via_intent(r, L) for r in R]))
    # Descriptive only, no test was pre-registered: with the artifact reps excluded, how often does a
    # Q2 rep take more tokens to converge than a Q4 rep?
    kept = [r for r in R if (r["quant"], r["rep"]) not in ARTIFACT]
    a = [r["ttc"] for r in kept if r["quant"] in S.Q2]
    b = [r["ttc"] for r in kept if r["quant"] in S.Q4]
    print(f"artifact reps excluded, cross-class pairs with Q2 ttc > Q4 ttc: "
          f"{sum(x > y for x in a for y in b)}/{len(a) * len(b)}  (descriptive; half = no separation)")
    for r in R:
        if (r["quant"], r["rep"]) in REAL:
            print(f"clean non-ceiling rep {r['quant']} r{r['rep']}: "
                  f"gain intent {r['gi']:+d}, goal {r['gg']:+d}, effect {r['fx']:+d}")
    for name, qs in (("Q2", S.Q2), ("Q4", S.Q4)):
        rs = [r for r in R if r["quant"] in qs]
        ok = sum(1 for r in rs if r["ceiling"] or (r["quant"], r["rep"]) in ARTIFACT)
        ttc = sorted(r["ttc"] for r in rs)
        print(f"{name}: {ok}/{len(rs)} first drawings structurally sound (ceiling, or failed only on artifacts); "
              f"ttc {[S.f(t, 0).strip() for t in ttc]}")

    print("\nEXPLORATORY (not pre-registered): change magnitude, intent2 vs goal2 from the same p1")
    pairs = []
    for q in S.ORDER:
        for rep in (1, 2, 3):
            png = lambda s: S.OUT / f"{q}_r{rep}_{s}.png"
            if all(png(s).exists() for s in ("p1", "intent2", "goal2")):
                ci, cg = E.change(png("p1"), png("intent2")), E.change(png("p1"), png("goal2"))
                if ci and cg:
                    pairs.append((q, rep, ci["changed_of_union"], cg["changed_of_union"]))
    for q, rep, i, g in pairs:
        more = "goal" if g > i else ("intent" if i > g else "tie")
        print(f"  {q:12s} r{rep}  intent {i:.3f}  goal {g:.3f}  -> {more} changed more")
    n = sum(1 for *_, i, g in pairs if i != g)
    k = sum(1 for *_, i, g in pairs if g > i)
    tail = sum(math.comb(n, j) for j in range(max(k, n - k), n + 1)) / 2 ** n
    d = [g - i for *_, i, g in pairs]
    print(f"  goal changed more in {k}/{n} pairs; mean paired diff {sum(d) / len(d):+.3f}; "
          f"two-sided exact sign test p = {min(1.0, 2 * tail):.2f}")


if __name__ == "__main__":
    main()
