#!/usr/bin/env python3
"""Grade the svgbench ladder against PREREG_BITDEPTH_FEEDBACK.md.

Mechanical on purpose: predictions were logged before the run, and reading results by eye is how
you talk yourself into the answer you expected. Every number traces to results.jsonl.
"""
import json, statistics
from pathlib import Path

OUT = Path("/mnt/TG_2TB/Projects/Apollo/data/receipts/svgbench-ladder")
Q2 = ("UD-Q2_K_XL", "UD-IQ2_M")
Q4 = ("UD-IQ4_XS", "UD-Q4_K_M")
ORDER = Q2 + Q4
INF = float("inf")


def latest():
    out, p = {}, OUT / "results.jsonl"
    if p.exists():
        for line in open(p):
            try:
                r = json.loads(line)
                out[(r.get("quant"), r.get("rep"), r.get("step"))] = r
            except Exception:
                pass
    return out


def mean(xs):
    xs = [x for x in xs if x is not None and x != INF]
    return sum(xs) / len(xs) if xs else None


def f(x, nd=2):
    if x is None:
        return "  —  "
    if x == INF:
        return " inf "
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def yn(x):
    # None means the step has not run -- it must not render as "N" (not identical).
    return "—" if x is None else ("Y" if x else "N")


def flips(a, b):
    if not a or not b:
        return [], []
    return ([k for k in a if not a[k] and b.get(k)], [k for k in a if a[k] and not b.get(k)])


def rows(L):
    out = []
    for q in ORDER:
        for rep in (1, 2, 3):
            p1 = L.get((q, rep, "p1"))
            if not p1 or p1.get("score") is None:
                continue
            s1, mx = p1["score"], p1.get("max")
            i2, g2, g3 = L.get((q, rep, "intent2")), L.get((q, rep, "goal2")), L.get((q, rep, "goal3"))
            sc = lambda r: r.get("score") if r else None
            ceiling = mx is not None and s1 == mx
            gi = sc(i2) - s1 if sc(i2) is not None else None
            gg = sc(g2) - s1 if sc(g2) is not None else None
            if ceiling:
                conv = 1
            elif g2 and sc(g2) is not None and g2.get("max") and sc(g2) == g2["max"]:
                conv = 2
            elif g3 and sc(g3) is not None and g3.get("max") and sc(g3) == g3["max"]:
                conv = 3
            else:
                conv = None
            tok = p1.get("tokens") or 0
            if conv is None:
                ttc = INF
            else:
                ttc = tok + ((g2 or {}).get("tokens") or 0 if conv >= 2 else 0) \
                          + ((g3 or {}).get("tokens") or 0 if conv >= 3 else 0)
            regress = [n for n, r, parent in (("intent2", i2, s1), ("goal2", g2, s1),
                                              ("goal3", g3, sc(g2)))
                       if r and sc(r) is not None and parent is not None and sc(r) < parent]
            out.append(dict(quant=q, rep=rep, p1=s1, max=mx, ceiling=ceiling, gi=gi, gg=gg,
                            fx=(gg - gi) if (not ceiling and gi is not None and gg is not None) else None,
                            conv=conv, ttc=ttc,
                            id_i=(i2 or {}).get("identical_to_parent"),
                            id_g=(g2 or {}).get("identical_to_parent"),
                            regress=regress,
                            flips_i=flips(p1.get("checks"), (i2 or {}).get("checks")),
                            flips_g=flips(p1.get("checks"), (g2 or {}).get("checks")),
                            steps=sum(1 for s in ("p1", "intent2", "goal2", "goal3") if L.get((q, rep, s)))))
    return out


def main():
    L = latest()
    R = rows(L)
    errs = [r for r in L.values() if r.get("error")]
    print(f"records: {len(L)}   graded reps: {len(R)}/12   errors: {len(errs)}")
    for e in errs:
        print(f"  ERROR {e.get('quant')} r{e.get('rep')} {e.get('step')}: {e.get('error')[:120]}")
    if not R:
        print("no completed first drawings yet")
        return
    print("\n quant        rep  p1   ceil  gain_i gain_g  effect conv  tok_to_conv  ident_i ident_g  regress")
    for r in R:
        print(f" {r['quant']:12s} {r['rep']}   {r['p1']:>2}/{r['max']}  {'Y' if r['ceiling'] else '.'}"
              f"   {f(r['gi'],0):>5}  {f(r['gg'],0):>5}  {f(r['fx'],0):>5}   {f(r['conv']):>3}"
              f"  {f(r['ttc'],0):>10}   {yn(r['id_i']):>5}   {yn(r['id_g']):>5}   {','.join(r['regress']) or '.'}")
    print("\n per-check flips (fixed / broken) by framing:")
    for r in R:
        fi, fg = r["flips_i"], r["flips_g"]
        if fi[0] or fi[1] or fg[0] or fg[1]:
            print(f"  {r['quant']} r{r['rep']}  intent +{fi[0]} -{fi[1]}   goal +{fg[0]} -{fg[1]}")

    cls = lambda qs: [r for r in R if r["quant"] in qs]
    nc = lambda rs: [r for r in rs if not r["ceiling"]]
    print("\n class   n  mean_p1  mean_gain_goal(non-ceil)  median_tok_to_conv")
    for name, qs in (("Q2", Q2), ("Q4", Q4)):
        rs = cls(qs)
        med = statistics.median([r["ttc"] for r in rs]) if rs else None
        print(f"  {name}    {len(rs)}   {f(mean([r['p1'] for r in rs]))}      "
              f"{f(mean([r['gg'] for r in nc(rs)]))}                  {f(med,0)}")

    print("\n PREDICTIONS (pre-registered; grading rules noted where a choice was needed)")
    eff = [r["fx"] for r in R if r["fx"] is not None]
    print(f"  P-L1 (60%) framing_effect > 0 over non-ceiling reps: n={len(eff)} mean={f(mean(eff))}  -> "
          + ("NOT EVALUABLE" if not eff else ("CONFIRMED" if mean(eff) > 0 else "FALSIFIED")))
    p2, p4 = mean([r["p1"] for r in cls(Q2)]), mean([r["p1"] for r in cls(Q4)])
    print(f"  P-L2 (60%) mean p1 Q2 < Q4: {f(p2)} vs {f(p4)}  -> "
          + ("NOT EVALUABLE" if None in (p2, p4) else ("CONFIRMED" if p2 < p4 else "FALSIFIED")))
    t2 = statistics.median([r["ttc"] for r in cls(Q2)]) if cls(Q2) else None
    t4 = statistics.median([r["ttc"] for r in cls(Q4)]) if cls(Q4) else None
    print(f"  P-L3 (55%) median tokens_to_converge Q2 > Q4: {f(t2,0)} vs {f(t4,0)}  -> "
          + ("NOT EVALUABLE" if None in (t2, t4) else ("CONFIRMED" if t2 > t4 else "FALSIFIED"))
          + "   [rule, NOT pre-specified: unconverged reps count as +inf]")
    g2c, g4c = mean([r["gg"] for r in nc(cls(Q2))]), mean([r["gg"] for r in nc(cls(Q4))])
    rd = lambda hi, lo: (hi - lo) / hi if (hi not in (None, 0) and lo is not None) else None
    dg, dp = rd(g4c, g2c), rd(p4, p2)
    print(f"  P-L4 (50%) rel drop in goal gain > rel drop in p1: gain {f(dg)} vs p1 {f(dp)}  -> "
          + ("NOT EVALUABLE (Q4 goal gain is zero/undefined, or a class is missing)" if None in (dg, dp)
             else ("CONFIRMED" if dg > dp else "FALSIFIED")))
    ii = [r["id_i"] for r in R if r["id_i"] is not None]
    ig = [r["id_g"] for r in R if r["id_g"] is not None]
    ri, rg = (sum(ii) / len(ii) if ii else None), (sum(ig) / len(ig) if ig else None)
    print(f"  P-L5 (65%) identical_to_parent rate intent > goal: {f(ri)} vs {f(rg)}  -> "
          + ("NOT EVALUABLE" if None in (ri, rg) else ("CONFIRMED" if ri > rg else "FALSIFIED")))
    print("\n  note: Q4_K_M wall times are excluded from any time comparison (1.08 GB host spill).")


if __name__ == "__main__":
    main()
