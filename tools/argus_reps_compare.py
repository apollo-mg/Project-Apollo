#!/usr/bin/env python3
"""Paired multi-rep comparison of two argus arms, as per-item pass RATES.

Never majority votes: RESULT_A1_SIZING_DISCORDANCE measured voting suppressing
discordance 12.5% -> 0%. Pass depends on the item's expectation kind. Two void
rules are reported because the published noise floor and the judge disagree:

  noisefloor  void = INFRA, TOOL-FAIL, SUSPECT, NO-ATTEMPT   -- reproduces
              RESULT_NOISE_FLOOR exactly (29 scorable, 3/29 = 10.3%)
  judge       void = INFRA, TOOL-FAIL only -- driver.judge() calls NO-ATTEMPT
              "a real failure" and SUSPECT is a grounding failure

IN-RUN NOISE FLOOR. With n reps per arm, an item passing k of n has k(n-k) discordant
rep-pairs out of C(n,2); summed over items that is an unbiased estimate of the
probability two independent draws of the SAME arm disagree (E = 2p(1-p)). The
between-arm analogue uses all n_A x n_B cross pairs. Equal models => between ~= within;
different models => between exceeds within by the per-item divergence (p_A - p_B)^2.
This is the instrument-level null test, and it needs no second run.

SELF-CHECK (2026-09-22): reproduces RESULT_NOISE_FLOOR cell-for-cell from its raw files
(29 scorable, 22/2/1/4, 82.8% vs 79.3%, 3/29 = 10.3%); t_sf matches scipy's 2*t.sf to
5 decimals at (t, df) = (0.57, 28), (2.1, 30), (3.4, 29), (1.0, 5).

usage: argus_reps_compare.py A.jsonl B.jsonl [--reps 1,2,3,4] [--labels A,B]
"""
import argparse, json, math, random, statistics as st
from collections import defaultdict

PASS = {"actions": {"CORRECT"}, "no_action": {"CORRECT"}, "no_action_ask": {"CLARIFIED"}}
VOIDS = {"noisefloor": {"INFRA", "TOOL-FAIL", "SUSPECT", "NO-ATTEMPT"},
         "judge": {"INFRA", "TOOL-FAIL"}}

def load(path, reps):
    out = defaultdict(dict)
    for line in open(path):
        r = json.loads(line)
        rep = r.get("rep") or 1          # rows written before --rep existed are single-rep runs
        if rep in reps:
            out[r["id"]][rep] = r
    return out

def t_sf(t, df):   # two-sided p for Student t, via regularized incomplete beta
    x = df / (df + t * t)
    return betainc(df / 2, 0.5, x)

def betainc(a, b, x):  # continued fraction (Numerical Recipes), enough for p-values
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b + lbeta)
    def cf(a, b, x):
        f, c, d = 1.0, 1.0, 0.0
        for i in range(400):
            m = i // 2
            if i == 0: num = 1.0
            elif i % 2 == 0: num = m * (b - m) * x / ((a + 2*m - 1) * (a + 2*m))
            else: num = -((a + m) * (a + b + m) * x) / ((a + 2*m) * (a + 2*m + 1))
            d = 1 + num * d; d = 1 / d if abs(d) > 1e-30 else 1e30
            c = 1 + num / c if abs(c) > 1e-30 else 1e30
            f *= c * d
            if abs(c * d - 1) < 1e-12: break
        return f
    if x < (a + 1) / (a + b + 2):
        return front * (cf(a, b, x) - 1) / a
    return 1 - math.exp(math.log(1 - x) * b + math.log(x) * a + lbeta) * (cf(b, a, 1 - x) - 1) / b

def analyse(A, B, meta, reps, void, labels, seed=0):
    items = [i for i in meta if meta[i].get("role") != "gate"]
    rows, pooled = [], {labels[0]: [0, 0], labels[1]: [0, 0]}
    rep_disc = []
    for rep in reps:
        b = c = n = 0
        for i in items:
            ra, rb = A.get(i, {}).get(rep), B.get(i, {}).get(rep)
            if not ra or not rb or ra["verdict"] in void or rb["verdict"] in void: continue
            k = meta[i]["expect"]["kind"]; pa = ra["verdict"] in PASS[k]; pb = rb["verdict"] in PASS[k]
            n += 1; b += pa and not pb; c += pb and not pa
        rep_disc.append((rep, n, b, c))
    for i in items:
        k = meta[i]["expect"]["kind"]
        va = [A[i][r]["verdict"] for r in reps if r in A.get(i, {}) and A[i][r]["verdict"] not in void]
        vb = [B[i][r]["verdict"] for r in reps if r in B.get(i, {}) and B[i][r]["verdict"] not in void]
        if not va or not vb: continue
        ra = sum(v in PASS[k] for v in va) / len(va); rb = sum(v in PASS[k] for v in vb) / len(vb)
        rows.append((i, k, ra, rb, len(va), len(vb)))
        pooled[labels[0]][0] += sum(v in PASS[k] for v in va); pooled[labels[0]][1] += len(va)
        pooled[labels[1]][0] += sum(v in PASS[k] for v in vb); pooled[labels[1]][1] += len(vb)
    # in-run noise floor: within-arm vs between-arm discordance over all rep-pairs
    wA = wAn = wB = wBn = bt = btn = 0
    for _, _, ra, rb, na, nb in rows:
        ka, kb = round(ra * na), round(rb * nb)
        wA += ka * (na - ka); wAn += na * (na - 1) // 2
        wB += kb * (nb - kb); wBn += nb * (nb - 1) // 2
        bt += ka * (nb - kb) + (na - ka) * kb; btn += na * nb
    floor = dict(within_A=(wA / wAn if wAn else float("nan"), wA, wAn),
                 within_B=(wB / wBn if wBn else float("nan"), wB, wBn),
                 between=(bt / btn if btn else float("nan"), bt, btn))
    d = [rb - ra for _, _, ra, rb, _, _ in rows]
    n = len(d); md = st.mean(d); sd = st.stdev(d) if n > 1 else 0.0
    t = md / (sd / math.sqrt(n)) if sd > 0 else 0.0
    p = t_sf(abs(t), n - 1) if sd > 0 else 1.0
    tcrit = {29: 2.045, 30: 2.042, 28: 2.048, 27: 2.052, 26: 2.056}.get(n - 1, 2.04)
    ci = (md - tcrit * sd / math.sqrt(n), md + tcrit * sd / math.sqrt(n))
    rng = random.Random(seed); boots = []
    for _ in range(20000):
        s = [d[rng.randrange(n)] for _ in range(n)]; boots.append(sum(s) / n)
    boots.sort(); bci = (boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots))])
    nz = [x for x in d if x != 0]
    return dict(items=n, mean_diff=md, sd=sd, t=t, p=p, ci95=ci, boot95=bci,
                items_B_better=sum(x > 0 for x in d), items_A_better=sum(x < 0 for x in d),
                items_tied=sum(x == 0 for x in d), nonzero=len(nz),
                pooled={k: (v[0] / v[1] if v[1] else float("nan"), v[0], v[1]) for k, v in pooled.items()},
                rep_disc=rep_disc, rows=rows, floor=floor)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--reps", default="1,2,3,4"); ap.add_argument("--labels", default="A,B")
    ap.add_argument("--families", default="argus/families_v4.json")
    ap.add_argument("--rows", action="store_true", help="print per-item rates")
    g = ap.parse_args()
    reps = [int(x) for x in g.reps.split(",")]; labels = g.labels.split(",")
    fam = json.load(open(g.families)); items = fam if isinstance(fam, list) else fam.get("items", fam.get("scenarios", []))
    meta = {i["id"]: i for i in items}
    A, B = load(g.a, reps), load(g.b, reps)
    for name, void in VOIDS.items():
        r = analyse(A, B, meta, reps, void, labels)
        print(f"=== void rule: {name}  ({', '.join(sorted(void))}) ===")
        for lab, (rate, k, n) in r["pooled"].items():
            print(f"  pooled pass  {lab:12s} {rate:6.1%}  ({k}/{n} item-reps)")
        print(f"  items {r['items']}   mean(B-A) per-item rate = {r['mean_diff']:+.3f}   sd {r['sd']:.3f}")
        print(f"  paired t = {r['t']:+.2f}, df {r['items']-1}, p = {r['p']:.3f}")
        print(f"  95% CI (t)         [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]")
        print(f"  95% CI (bootstrap) [{r['boot95'][0]:+.3f}, {r['boot95'][1]:+.3f}]")
        print(f"  items B better {r['items_B_better']}, A better {r['items_A_better']}, tied {r['items_tied']}")
        print("  per-rep discordance (n, b=A-only, c=B-only):",
              "  ".join(f"r{rep}: {b+c}/{n}={((b+c)/n if n else 0):.1%}" for rep, n, b, c in r["rep_disc"]))
        f = r["floor"]
        print(f"  in-run floor: within-{labels[0]} {f['within_A'][0]:.1%} ({f['within_A'][1]}/{f['within_A'][2]} pairs)"
              f"   within-{labels[1]} {f['within_B'][0]:.1%} ({f['within_B'][1]}/{f['within_B'][2]})"
              f"   BETWEEN {f['between'][0]:.1%} ({f['between'][1]}/{f['between'][2]})")
        tb = sum(b + c for _, _, b, c in r["rep_disc"]); tn = sum(n for _, n, _, _ in r["rep_disc"])
        print(f"  same-index rep pairing, pooled: {tb}/{tn} = {tb/tn:.1%}")
        if g.rows:
            for i, k, ra, rb, na, nb in sorted(r["rows"], key=lambda x: x[3] - x[2]):
                if ra != rb: print(f"      {i:22s} {k:14s} A {ra:.2f} (n{na})  B {rb:.2f} (n{nb})  d {rb-ra:+.2f}")
        print()

if __name__ == "__main__":
    main()
