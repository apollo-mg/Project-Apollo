#!/usr/bin/env python3
"""DESCRIPTIVE ONLY, not pre-registered: could Mark's 4-bit lean come from drawings he had seen
before rating? The transcript shows six of the ten first drawings displayed in-session, with the
quant in the file name, before the blind page existed; the one he described ("color, cloud, and
sun", 00:00 UTC) followed a view of UD-IQ4_XS r1 at 23:50 UTC."""
import itertools, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/tools/svgbench")
import score_blind as S
SHOWN = {("UD-Q2_K_XL", 1), ("UD-IQ2_M", 1), ("UD-IQ4_XS", 1), ("UD-Q2_K_XL", 2), ("UD-IQ2_M", 2), ("UD-IQ4_XS", 2)}
code = lambda q, r: next(c for c in S.FIRST if S.DRAW[c]["quant"] == q and S.DRAW[c]["rep"] == r)

def lean(J, keep):
    vals = {k: v for k, v in S.first_values(J).items() if k[0] in keep and k[1] in keep}
    rates = S.win_rates(vals)
    q4 = [c for c in keep if S.DRAW[c]["quant"] in S.Q4]
    def stat(s):
        q2 = [c for c in keep if c not in s]
        return sum(1.0 if rates[b] > rates[a] else 0.5 if rates[b] == rates[a] else 0.0 for a in q2 for b in s)
    obs, n = stat(q4), len(q4) * (len(keep) - len(q4))
    sets = [stat(list(s)) for s in itertools.combinations(keep, len(q4))]
    p = sum(abs(s - n / 2) >= abs(obs - n / 2) - 1e-9 for s in sets) / len(sets)
    return obs, n, p, len(sets), rates

Jm, _, _ = S.load_mark(S.D / "picks_mark")
described = code("UD-IQ4_XS", 1)
shown = {code(q, r) for q, r in SHOWN}
for name, keep in [("all ten (the pre-registered P-B1)", list(S.FIRST)),
                   (f"without the described drawing {described} ({S.label(described)})", [c for c in S.FIRST if c != described]),
                   ("without UVR7 (my first, wrong guess at the described drawing)", [c for c in S.FIRST if c != "UVR7"]),
                   ("only the four never displayed in-session", [c for c in S.FIRST if c not in shown])]:
    obs, n, p, k, rates = lean(Jm, keep)
    print(f"{name}:\n   4-bit ahead in {obs:g}/{n}, exact permutation p = {p:.3f} over {k} label sets"
          + ("  [too few drawings for the test to mean anything]" if k < 20 else ""))
    if len(keep) <= 4:
        for c in sorted(rates, key=lambda c: -rates[c]):
            print(f"     {c} {rates[c]:.3f} {S.label(c)}")
