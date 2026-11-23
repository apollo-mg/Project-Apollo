#!/usr/bin/env python3
"""PREREG_PI_HERMES.md analysis (written after the run; the prereg fixed the pass rule, voids, unit and tests).
Pass: CORRECT for act and answer-only items, CLARIFIED for ask items (tools/argus_reps_compare.py). Voids: INFRA and
TOOL-FAIL, except a timeout (INFRA with TimeoutError), which is a failure. An item is dropped if either arm is void;
a template's score is the mean pass over its remaining items; unit = template (world-B twins share their template).
Usage: analyze_pi_hermes.py RAW_DIR   (RAW_DIR holds BASE.jsonl and PIA.jsonl)"""
import itertools, json, math, random, re, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "raw"
SC = {s["id"]: s for s in json.load(open(ROOT / "argus" / "families_v5.json"))["scenarios"]}
PASS = {"actions": {"CORRECT"}, "no_action": {"CORRECT"}, "no_action_ask": {"CLARIFIED"}}
tmpl = lambda i: re.sub(r"^B-", "", i)


def load(arm):
    return {r["id"]: r for r in map(json.loads, open(RAW / f"{arm}.jsonl"))}


def void(r):
    return r["verdict"] in ("INFRA", "TOOL-FAIL") and "TimeoutError" not in (r.get("why") or "")


def passed(r):
    return r["verdict"] in PASS[SC[r["id"]]["expect"]["kind"]]


def tcrit(df, two_sided_alpha):
    # t quantiles for the df we can get (<= 43 clusters), by bisection on the regularised incomplete beta via math.lgamma
    def cdf(t):
        x = df / (df + t * t)
        # incomplete beta by continued fraction (Numerical Recipes betacf)
        a, b = df / 2, 0.5
        lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        def betacf(x):
            qab, qap, qam, c, d = a + b, a + 1, a - 1, 1.0, 1 - (a + b) * x / (a + 1)
            d = 1 / (d if abs(d) > 1e-30 else 1e-30); h = d
            for m in range(1, 300):
                m2 = 2 * m; aa = m * (b - m) * x / ((qam + m2) * (a + m2))
                d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30); c = 1 + aa / c if abs(1 + aa / c) > 1e-30 else 1e-30; h *= d * c
                aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
                d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30); c = 1 + aa / c if abs(1 + aa / c) > 1e-30 else 1e-30
                de = d * c; h *= de
                if abs(de - 1) < 1e-12: break
            return h
        ib = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta) * betacf(x) / a
        return 1 - 0.5 * ib if t > 0 else 0.5 * ib
    lo, hi, target = 0.0, 20.0, 1 - two_sided_alpha / 2
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) < target else (lo, mid)
    return (lo + hi) / 2


def summarize(d, label):
    n = len(d)
    if n < 2:
        print(f"- {label}: n = {n}, no test"); return None
    m, sd = statistics.mean(d), statistics.stdev(d)
    se = sd / math.sqrt(n)
    c95, c90 = tcrit(n - 1, 0.05) * se, tcrit(n - 1, 0.10) * se
    nz = [x for x in d if x != 0]
    obs = abs(sum(nz))
    if len(nz) <= 20:
        tot = ext = 0
        for signs in itertools.product((1, -1), repeat=len(nz)):
            tot += 1; ext += abs(sum(s * x for s, x in zip(signs, nz))) >= obs - 1e-12
        p = ext / tot
    else:
        rng = random.Random(20261123); k = 200000
        p = sum(abs(sum(x if rng.random() < 0.5 else -x for x in nz)) >= obs - 1e-12 for _ in range(k)) / k
    print(f"- {label}: {n} templates, mean PIA - BASE {m * 100:+.1f} pp, 95% CI [{(m - c95) * 100:+.1f}, {(m + c95) * 100:+.1f}], "
          f"90% CI [{(m - c90) * 100:+.1f}, {(m + c90) * 100:+.1f}], sign-flip p = {p:.4f} ({len(nz)} templates differ)")
    return m, m - c90, m + c90, p


def main():
    B, P = load("BASE"), load("PIA")
    ids = sorted(set(B) & set(P))
    print(f"# pi adapter in Hermes: {len(B)} BASE rows, {len(P)} PIA rows, {len(ids)} paired\n")
    for a, R in (("BASE", B), ("PIA", P)):
        by = defaultdict(list)
        for i in ids:
            if not void(R[i]):
                by[SC[i]["expect"]["kind"]].append(passed(R[i]))
        tot = [x for v in by.values() for x in v]
        print(f"- {a}: pass {sum(tot)}/{len(tot)}; " + ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(by.items()))
              + f"; verdicts {dict(Counter(R[i]['verdict'] for i in ids))}; timeouts {sum('TimeoutError' in (R[i].get('why') or '') for i in ids)}; "
              f"median secs {statistics.median(float(R[i]['secs']) for i in ids):.0f}; mean backend calls "
              f"{statistics.mean(int(R[i]['backend_calls'] or 0) for i in ids):.1f}")
    keep = [i for i in ids if not void(B[i]) and not void(P[i])]
    print(f"- voided items (either arm): {len(ids) - len(keep)}")

    def cluster_diffs(kinds):
        T = defaultdict(lambda: ([], []))
        for i in keep:
            if SC[i]["expect"]["kind"] in kinds:
                T[tmpl(i)][0].append(passed(B[i])); T[tmpl(i)][1].append(passed(P[i]))
        return [statistics.mean(p) - statistics.mean(b) for b, p in T.values()]

    print("\n## Predictions\n")
    r1 = summarize(cluster_diffs({"actions", "no_action", "no_action_ask"}), "H1 overall")
    if r1:
        m, lo, hi, p = r1
        print(f"  H1 -> {'EQUIVALENT (does not ruin it)' if -0.10 <= lo and hi <= 0.10 else ('it HURTS Hermes' if m < 0 and p < 0.05 else ('it HELPS' if m > 0 and p < 0.05 else 'not equivalent, no significant direction'))}")
    r2 = summarize(cluster_diffs({"no_action_ask"}), "H2 ask templates")
    if r2:
        print(f"  H2 (PIA passes fewer ask items) -> {'holds' if r2[0] < 0 else 'FAILS'}")
    r3 = summarize(cluster_diffs({"actions"}), "H3 act templates")
    if r3:
        print(f"  H3 (act side no worse than -5 pp) -> {'holds' if r3[0] >= -0.05 else 'FAILS'}")
    summarize(cluster_diffs({"no_action"}), "answer-only templates (no prediction)")

    print("\n## Items where the arms differ (pass)")
    for i in keep:
        if passed(B[i]) != passed(P[i]):
            print(f"  {i:24s} {SC[i]['expect']['kind']:14s} BASE {B[i]['verdict']:15s} PIA {P[i]['verdict']}")
    print("\n## By family (pass, BASE / PIA, non-void pairs)")
    fam = defaultdict(lambda: [0, 0, 0])
    for i in keep:
        f = SC[i]["family"]; fam[f][0] += passed(B[i]); fam[f][1] += passed(P[i]); fam[f][2] += 1
    for f, (b, p, n) in sorted(fam.items()):
        print(f"  {f:32s} {b}/{n}  {p}/{n}")


if __name__ == "__main__":
    main()
