#!/usr/bin/env python3
"""Score the DIMM pre/post-upgrade baseline from flashnext_residency.py's results.jsonl.

Implements the rule preregistered in PREREG_DIMM_UPGRADE.md Amendments 3 and 4 -- nothing here
is a free parameter chosen after the data:

  * per launch (L0/L1/L2), median decode over reps 1,2  (rep 0 discarded: warmup never faults the
    spilled experts, it is a known 4-10% bias, not noise). A launch with <2 of {rep1,rep2} is dropped.
  * per (rung, ctx): median AND full spread (max-min) across the 3 launch medians. The spread is the
    only error bar the after-run has.
  * P-D5 fork threshold, per ctx, from the frozen before-medians:
        spill(c)   = t48(c) - t2(c)                     [ms/token; = the prereg's 71.3 ms at ctx 500]
        after(c)   = t2(c)  + spill(c) / B              [B = 1.54, the P-D2 node-local bandwidth floor]
        s(c)       = t48(c) / after(c)                  [predicted rung-48 speedup]
    where t2, t48 are 1000/median_tok_s. Reproduces +27% at ctx 500 by construction.
  * unmeasurability clause: if the rung-48 across-launch spread at ctx c (as a fraction of its median)
    is >= s(c)-1, P-D5 is UNMEASURABLE by this method at that ctx -- the lottery drowns the fork.

Usage:  score_dimm.py <results.jsonl> [DB|DA]      default prefix DB (the "before")
"""
import json, statistics, sys, re

B_FLOOR = 1.54            # P-D2: node-local triad rises 22.68 -> >=35 GB/s  => >= 1.543x
CTXS = (500, 1800, 3600)
RUNGS = (2, 16, 48)


def load(path, prefix):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    gates = [r for r in rows if r.get("stage") == "gates" and r.get("run_stage") in ("db", "da")]
    # req rows: arm like DB-02-L0 -> rung 2, launch 0
    data = {}   # (rung, launch, ctx) -> {rep: tg}
    pat = re.compile(rf"^{prefix}-(\d+)-L(\d+)$")
    for r in rows:
        if r.get("stage") != "req":
            continue
        m = pat.match(r.get("arm", ""))
        if not m:
            continue
        rung, launch, ctx, rep = int(m.group(1)), int(m.group(2)), r["len"], r["rep"]
        tg = r.get("tg_tps")
        if tg is None:
            continue
        data.setdefault((rung, launch, ctx), {})[rep] = tg
    return gates, data


def launch_median(reps):
    # reps 1 and 2 only; rep 0 discarded. Require both.
    vals = [reps[k] for k in (1, 2) if k in reps]
    if len(vals) < 2:
        return None
    return statistics.median(vals)


def score(path, prefix):
    gates, data = load(path, prefix)
    # collapse to per (rung, ctx): list of launch medians
    agg = {}
    for (rung, launch, ctx), reps in data.items():
        lm = launch_median(reps)
        if lm is None:
            continue
        agg.setdefault((rung, ctx), {})[launch] = lm

    print(f"=== DIMM baseline '{prefix}' — {path}")
    if gates:
        g = gates[-1]
        print(f"driver_sha={g.get('driver_sha','?')[:16]}  clocks={g.get('clocks','').splitlines()[0] if g.get('clocks') else '?'}")
    print(f"scoring rule: reps 1,2 (rep0 discarded); across L0/L1/L2 median & spread; B={B_FLOOR}\n")

    med = {}   # (rung, ctx) -> median across launches
    for ctx in CTXS:
        print(f"--- ctx {ctx} ---")
        for rung in RUNGS:
            lm = agg.get((rung, ctx), {})
            vals = [lm[k] for k in sorted(lm)]
            if not vals:
                print(f"  rung {rung:2d}: NO DATA")
                continue
            m = statistics.median(vals)
            spread = max(vals) - min(vals)
            med[(rung, ctx)] = m
            per = "  ".join(f"L{k}={lm[k]:.2f}" for k in sorted(lm))
            print(f"  rung {rung:2d}: {per}   median={m:.2f} tok/s   spread={spread:.2f} ({100*spread/m:.1f}%)")
        print()

    print("=== P-D5 fork threshold (derived from these frozen before-medians) ===")
    for ctx in CTXS:
        if (2, ctx) not in med or (48, ctx) not in med:
            continue
        r2, r48 = med[(2, ctx)], med[(48, ctx)]
        t2, t48 = 1000 / r2, 1000 / r48
        spill = t48 - t2
        after = t2 + spill / B_FLOOR
        s = t48 / after
        rise = s - 1
        # rung-48 spread as fraction of its median
        lm48 = agg.get((48, ctx), {})
        v48 = [lm48[k] for k in sorted(lm48)]
        spread48 = (max(v48) - min(v48)) / med[(48, ctx)] if v48 else float("nan")
        verdict = "UNMEASURABLE (spread >= predicted rise)" if spread48 >= rise else "measurable"
        print(f"  ctx {ctx}: r2={r2:.2f} r48={r48:.2f}  spill=t48-t2={spill:.1f}ms  "
              f"predict {r48:.2f}->{1000/after:.2f} tok/s (+{100*rise:.1f}%)  "
              f"rung48 spread={100*spread48:.1f}%  -> {verdict}")
    # spill ctx-stability check
    spills = [ (1000/med[(48,c)] - 1000/med[(2,c)]) for c in CTXS if (2,c) in med and (48,c) in med ]
    if spills:
        print(f"\nspill(c) across ctx = {[round(x,1) for x in spills]} ms  "
              f"(prereg spill=71.3ms; ~ctx-stable validates the rung-2 'no host traffic' assumption)")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "dimm_results.jsonl"
    prefix = sys.argv[2] if len(sys.argv) > 2 else "DB"
    score(path, prefix)
