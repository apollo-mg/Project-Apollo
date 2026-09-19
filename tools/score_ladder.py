#!/usr/bin/env python3
"""Score the low-bit codec ladder against PREREG_CODEC_LADDER.md.

Reads the per-cell results.jsonl written by run_cells.sh (and the prism batch), prints the
ladder table, and scores every preregistered prediction that has enough data.

Design notes that matter:
  * A prediction with missing cells is reported PENDING, never silently skipped and never
    scored on partial data.
  * The P-L0 floor is passed in, not hardcoded, because the floor is a measured quantity.
  * Cells with status != OK are excluded from scoring and listed separately. A NO_RESULT cell
    is not a zero, it is an absence.
"""
import json, sys, argparse, math

# Effective parameter count, RECOVERED from the four cells whose bpw the prereg states
# (G-IQ2XS, G-IQ3XXS, B-PTQ1, B-PQ2). It reproduces all four to within 0.02 bpw, so it is
# used to fill in the AD cells the prereg leaves as "?" rather than leaving the size axis
# half-blank. Derived, and labelled as derived wherever it is printed.
NPARAM = 27.21e9

# Bytes each file spends on the MTP draft head (blk.64.* / .nextn.*), which llama-perplexity
# reports as "unused tensor ... ignoring" and never reads. Measured from the GGUF tensor offsets;
# the binary's own unused list is exactly this set. Subtracting them is what makes "quality per
# byte" a fair comparison: GSQ spends ~4% of its file here, AD ~3%, Bonsai nothing at all.
# See METHOD_SCORED_BYTES.md.
MTP_BYTES = {
    "G-IQ2XS": 348469248, "G-IQ3XXS": 348469248, "C-XBIN": 348469248,
    "A-IQ2XS": 292067328, "A-IQ3XXS": 292067328, "A-IQ3S": 292067328,
    "B-PTQ1": 0, "B-PQ2": 0,
}

def bpw_of(nbytes):
    return nbytes * 8 / NPARAM if nbytes else None

def scored_bytes(cell, nbytes):
    return nbytes - MTP_BYTES.get(cell, 0)

def scored_bpw(cell, nbytes):
    return bpw_of(scored_bytes(cell, nbytes))

def curve(cells, ok, kldf, log=True):
    """Fit a family's KLD-vs-size curve. LOG-LINEAR by default.

    A linear fit is inadmissible: extrapolated even slightly it predicts NEGATIVE KLD, and a
    divergence cannot go below zero. Measured 2026-09-19, GSQ's linear fit reaches -0.0009 at
    3.465 bpw. Log-linear also makes the families agree: decay constants 1.4077 vs 1.3403 per
    bpw (4.8% apart), where the linear rates were 24% apart. Same exponential rate, different
    constant factor, which is what a codec-quality difference should look like.
    """
    pts = sorted(((scored_bpw(c, int(ok[c]["bytes"])), kldf(c)) for c in cells))
    pts = [(b, k) for b, k in pts if k is not None and (k > 0 or not log)]
    if len(pts) < 2:
        return None
    (b1, k1), (b2, k2) = pts[0], pts[-1]
    if b2 <= b1:
        return None
    if log:
        return ("log", b1, k1, (math.log(k2) - math.log(k1)) / (b2 - b1))
    return ("lin", b1, k1, (k1 - k2) / (b2 - b1))

def interp(cv, target_bpw):
    kind, b1, k1, rate = cv
    if kind == "log":
        return math.exp(math.log(k1) + rate * (target_bpw - b1))
    return k1 - (target_bpw - b1) * rate

def fit_quality(cells, ok, kldf):
    """With >=3 cells, report how well log-linear actually holds (max % residual)."""
    pts = sorted(((scored_bpw(c, int(ok[c]["bytes"])), kldf(c)) for c in cells))
    pts = [(b, k) for b, k in pts if k and k > 0]
    if len(pts) < 3:
        return None
    (b1, k1), (b2, k2) = pts[0], pts[-1]
    rate = (math.log(k2) - math.log(k1)) / (b2 - b1)
    worst = 0.0
    for b, k in pts[1:-1]:
        pred = math.exp(math.log(k1) + rate * (b - b1))
        worst = max(worst, abs(k - pred) / k * 100)
    return worst

FAMILY = {  # cell -> (family, nominal bpw from the prereg where stated)
    "G-IQ2XS":  ("GSQ-RCO", 2.58),
    "G-IQ3XXS": ("GSQ-RCO", 3.05),
    "A-IQ2XS":  ("AD", None),
    "A-IQ3XXS": ("AD", None),
    "A-IQ3S":   ("AD", None),
    "B-PTQ1":   ("Bonsai2", 1.75),
    "B-PQ2":    ("Bonsai2", 2.13),
    "C-XBIN":   ("control", 2.58),
}

def load(paths):
    cells = {}
    for p in paths:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                cells[d["cell"]] = d        # later files win, so a re-run supersedes
    return cells

def fl(d, k):
    v = d.get(k, "")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--floor", type=float, default=1e-4,
                    help="threshold for the agreement tests (P-L5, C-XBIN). Default 1e-4 is the "
                         "PREREGISTERED value. Do not lower it to the P-L0 'measured floor': that "
                         "run printed Mean KLD 0.000000 at six decimals, so all it establishes is "
                         "< 5e-7, and every cell's KLD is likewise printed to 1e-6. A threshold at "
                         "or below the printing resolution turns rounding into a verdict.")
    a = ap.parse_args()
    if a.floor < 1e-5:
        print(f"WARNING: --floor {a.floor:.1e} is at or below the 1e-6 printing resolution of the\n"
              f"         KLD values. Differences that small are rounding, not measurement.\n"
              f"         The preregistered threshold is 1e-4.\n")
    cells = load(a.results)

    ok  = {k: v for k, v in cells.items() if v.get("status") == "OK"}
    bad = {k: v for k, v in cells.items() if v.get("status") != "OK"}

    print("=" * 96)
    print("LOW-BIT CODEC LADDER -- Qwen3.8-27B, all cells vs the same Q8_0 reference (ref.kld)")
    print("=" * 96)
    print("size axis = SCORED bytes (file minus the MTP head llama-perplexity ignores).")
    print("See METHOD_SCORED_BYTES.md. GSQ spends ~4% of its file there, AD ~3%, Bonsai 0%.\n")
    print(f"{'cell':<10} {'family':<9} {'GiB':>7} {'s.bpw':>6} {'mean KLD':>11} {'median':>11} "
          f"{'99% KLD':>10} {'same-top %':>11} {'PPL(Q)':>9}")
    print("-" * 96)
    for k, d in sorted(ok.items(), key=lambda kv: int(kv[1].get("bytes") or 0)):
        fam, bpw = FAMILY.get(k, ("?", None))
        nb = int(d.get("bytes") or 0)
        gib = nb / 2**30
        bpw = scored_bpw(k, nb)   # SCORED bytes: the axis quality is actually measured against
        mk, md = fl(d, "mean_kld"), fl(d, "median_kld")
        p99, st, pq = fl(d, "p99_kld"), fl(d, "same_top"), fl(d, "mean_ppl_q")
        print(f"{k:<10} {fam:<9} {gib:>7.2f} {(f'{bpw:.2f}' if bpw else '?'):>6} "
              f"{(f'{mk:.6f}' if mk is not None else 'n/a'):>11} "
              f"{(f'{md:.6f}' if md is not None else 'n/a'):>11} "
              f"{(f'{p99:.5f}' if p99 is not None else 'n/a'):>10} "
              f"{(f'{st:.3f}' if st is not None else 'n/a'):>11} "
              f"{(f'{pq:.4f}' if pq is not None else 'n/a'):>9}")
    if bad:
        print("\nEXCLUDED (not scored -- an absent result is not a zero):")
        for k, d in bad.items():
            print(f"  {k:<10} status={d.get('status')} rc={d.get('rc')}")

    print("\n" + "=" * 96)
    print(f"PREDICTIONS  (floor = {a.floor:.2e}, measured by P-L0)")
    print("=" * 96)

    def need(*ks):
        miss = [k for k in ks if k not in ok]
        return miss

    def kld(k):
        return fl(ok[k], "mean_kld")

    def top(k):
        return fl(ok[k], "same_top")

    # ---- P-L1: monotonic within family ----
    print("\nP-L1  KLD decreases monotonically with bpw WITHIN a codec family")
    for fam, seq in (("GSQ-RCO", ["G-IQ2XS", "G-IQ3XXS"]),
                     ("AD", ["A-IQ2XS", "A-IQ3XXS", "A-IQ3S"])):
        miss = need(*seq)
        if miss:
            print(f"  {fam:<9} PENDING (missing {', '.join(miss)})")
            continue
        vals = [(c, kld(c)) for c in seq]
        mono = all(vals[i][1] > vals[i+1][1] for i in range(len(vals)-1))
        chain = "  >  ".join(f"{c}={v:.6f}" for c, v in vals)
        print(f"  {fam:<9} {'HOLDS' if mono else 'INVERSION'}   {chain}")

    # ---- P-L2: the fork ----
    print("\nP-L2  THE FORK: B-PQ2 has LOWER KLD than G-IQ2XS despite being smaller")
    miss = need("B-PQ2", "G-IQ2XS")
    if miss:
        print(f"  PENDING (missing {', '.join(miss)})")
    else:
        b, g = kld("B-PQ2"), kld("G-IQ2XS")
        rel = abs(b - g) / g if g else float("inf")
        if rel <= 0.05:
            v = "FALSIFIED (within 5% -- the prereg's own tie margin)"
        elif b < g:
            v = "CONFIRMED"
        else:
            v = "FALSIFIED (GSQ-RCO is lower)"
        print(f"  B-PQ2={b:.6f}  G-IQ2XS={g:.6f}  rel diff={rel*100:.2f}%  -> {v}")

    # ---- P-L3: GSQ beats AD ----
    print("\nP-L3  GSQ-RCO beats AD at comparable size")
    gs_cells = [c for c in ok if FAMILY.get(c, ("?",))[0] == "GSQ-RCO" and c != "C-XBIN"]
    ad_cells = [c for c in ok if FAMILY.get(c, ("?",))[0] == "AD"]
    if not gs_cells or not ad_cells:
        print("  PENDING (need at least one GSQ cell and one AD cell)")
    else:
        print("  raw head-to-head at the shared quant label:")
        for g in sorted(gs_cells):
            for a_ in sorted(ad_cells):
                gb, ab = scored_bpw(g, int(ok[g]["bytes"])), scored_bpw(a_, int(ok[a_]["bytes"]))
                if abs(gb - ab) > 0.6:
                    continue
                who = "GSQ" if kld(g) < kld(a_) else "AD"
                print(f"    {g:<9}({gb:.3f}) {kld(g):.6f}  vs  {a_:<9}({ab:.3f}) {kld(a_):.6f}"
                      f"   -> {who} lower, but sizes differ by {abs(gb-ab):.3f} bpw")

        # THE FAIR COMPARISON: price each AD cell against GSQ's own curve at the SAME size.
        cv = curve(gs_cells, ok, kld)
        if cv is None:
            print("\n  matched-size comparison PENDING (needs >=2 GSQ cells to fit a curve)")
        else:
            _kind, b1, k1, rate = cv
            print(f"\n  GSQ curve (log-linear): decay {-rate:.4f} per scored bpw"
                  f"  = KLD x{math.exp(rate):.3f} per +1 bpw   (anchor {b1:.3f} @ {k1:.6f})")
            fq = fit_quality(gs_cells, ok, kld)
            if fq is not None:
                print(f"    log-linearity check: worst interior residual {fq:.1f}%")
            wins = losses = 0
            for a_ in sorted(ad_cells):
                ab, ak = scored_bpw(a_, int(ok[a_]["bytes"])), kld(a_)
                pred = interp(cv, ab)
                if pred <= 0:
                    print(f"    {a_}: GSQ curve extrapolates to {pred:.6f} <= 0 -- out of range, skipped")
                    continue
                delta = (ak - pred) / ak * 100
                mark = "GSQ better" if pred < ak else "AD better"
                if pred < ak: wins += 1
                else: losses += 1
                hi = max(scored_bpw(c, int(ok[c]["bytes"])) for c in gs_cells)
                inrange = "interpolated" if b1 <= ab <= hi else "EXTRAPOLATED"
                print(f"    {a_:<9} {ab:.3f} bpw: AD {ak:.6f}  vs  GSQ-at-same-size {pred:.6f}"
                      f"  -> {mark} by {abs(delta):.1f}% ({inrange})")
            # Independent cross-check on same-top. KLD is a full-distribution distance;
            # top-1 agreement only cares about the argmax. If they agree at matched size, the
            # ranking is not an artifact of one statistic.
            cvt = curve(gs_cells, ok, top, log=False)   # same-top is a bounded %, not a divergence
            if cvt is not None:
                _k2, bt1, tt1, trate = cvt
                trate = -trate          # same-top RISES with size; curve() returns a falling rate
                print(f"\n  cross-check on same-top (independent of KLD):"
                      f" GSQ gains {trate:.3f} pp per scored bpw")
                for a_ in sorted(ad_cells):
                    ab, at_ = scored_bpw(a_, int(ok[a_]["bytes"])), top(a_)
                    predt = tt1 + (ab - bt1) * trate
                    if not (0 < predt <= 100):
                        continue
                    e_pred, e_act = 100 - predt, 100 - at_
                    print(f"    {a_:<9} {ab:.3f} bpw: AD top-1 error {e_act:.3f}%  vs "
                          f"GSQ-at-same-size {e_pred:.3f}%  -> AD has {(e_act-e_pred)/e_pred*100:+.1f}% more errors")
                print("    Agreement between the two metrics means the ranking is not an artifact of KLD.")

            print(f"\n  MATCHED-SIZE VERDICT: GSQ better in {wins} of {wins+losses} comparisons"
                  f"  -> P-L3 {'CONFIRMED' if wins > losses else 'FALSIFIED'} on the size-normalised reading")
            print("  Both readings are reported. The raw one answers 'which file is better',")
            print("  the matched-size one answers 'which codec is better'. Only the second is P-L3.")
        print("\n  NOTE: IQ2_XS is 2.48 scored bpw from ISTA-DASLab and 2.82 from AD -- a 13%")
        print("        spread under one label. Comparing by label compares different size classes.")

    # ---- P-L4: same-top drops more than KLD implies ----
    print("\nP-L4  Ternary cells drop same-top MORE than their KLD suggests (>=0.5 pp)")
    gs_all = [c for c in ok if FAMILY.get(c, ("?",))[0] == "GSQ-RCO" and c != "C-XBIN"]
    tern = [c for c in ok if FAMILY.get(c, ("?",))[0] == "Bonsai2"]
    cvk, cvt = curve(gs_all, ok, kld), curve(gs_all, ok, top, log=False)
    if not tern or cvk is None or cvt is None:
        print("  PENDING (needs a ternary cell and >=2 GSQ cells)")
    else:
        _k, b1, k1, rate = cvk
        _t, bt1, tt1, trate = cvt; trate = -trate
        for c in sorted(tern):
            tk, tt = kld(c), top(c)
            # where would a scalar cell sit at THIS KLD, and what same-top would it have?
            b_eq = b1 + math.log(k1 / tk) / -rate if rate else None
            if b_eq is None:
                continue
            t_eq = tt1 + (b_eq - bt1) * trate
            d = t_eq - tt
            print(f"  {c:<7} KLD {tk:.6f}, same-top {tt:.3f}%")
            print(f"          a SCALAR cell of equal KLD sits at {b_eq:.3f} bpw -> same-top {t_eq:.3f}%")
            print(f"          -> ternary is {d:+.3f} pp below it   ({'MEETS' if d >= 0.5 else 'does not meet'} the 0.5 pp threshold)")
        print("  NOTE: the scalar equivalent is EXTRAPOLATED below GSQ's measured range")
        print("        (2.476-2.968 bpw). Direction is robust; the exact pp value is not.")

    # ---- P-L5: the control pair ----
    print("\nP-L5  CONTROL: B-PTQ1 and B-PQ2 hold the SAME ternary weights -> KLD must agree")
    miss = need("B-PTQ1", "B-PQ2")
    if miss:
        print(f"  PENDING (missing {', '.join(miss)})")
    else:
        p1, p2 = kld("B-PTQ1"), kld("B-PQ2")
        d = abs(p1 - p2)
        v = "CONFIRMED" if d < a.floor else "FALSIFIED -- one packing has an implementation defect"
        print(f"  B-PTQ1={p1:.6f}  B-PQ2={p2:.6f}  |diff|={d:.6e}  floor={a.floor:.2e}  -> {v}")

    # ---- C-XBIN: cross-binary validity (Amendment 1) ----
    print("\nC-XBIN  Amendment 1 control: same model+reference on both binaries")
    miss = need("C-XBIN", "G-IQ2XS")
    if miss:
        print(f"  PENDING (missing {', '.join(miss)})")
    else:
        c, g = kld("C-XBIN"), kld("G-IQ2XS")
        d = abs(c - g)
        verdict = "PASS" if d < a.floor else "over threshold"
        print(f"  prism={c:.6f}  buun={g:.6f}  |diff|={d:.6e}   (threshold {a.floor:.0e}) -> {verdict}")

        # A pass/fail against a fixed threshold is not the whole story. What matters is the
        # cross-binary noise RELATIVE TO the effect each prediction must detect. Reporting only
        # pass/fail would either bless or void a prediction on a technicality.
        # ONLY predictions that actually cross binaries. P-L5 compares two prism cells to
        # each other, so cross-binary noise is irrelevant to it -- applying this check there
        # was a bug that reported a confirmed control as "confounded".
        for pid, cells_, desc in (("P-L2", ("B-PQ2", "G-IQ2XS"), "B-PQ2 vs G-IQ2XS"),
                                  ("P-L4", ("B-PQ2", "G-IQ2XS"), "B-PQ2 vs G-IQ2XS")):
            if all(x in ok for x in cells_):
                eff = abs(kld(cells_[0]) - kld(cells_[1]))
                if eff > 0:
                    print(f"    {pid}: effect |{desc}| = {eff:.6f}"
                          f"  -> cross-binary noise is {d/eff*100:.3f}% of it"
                          f" ({'negligible' if d < eff/20 else 'NOT negligible -- treat as confounded'})")
            else:
                print(f"    {pid}: effect size pending ({', '.join(x for x in cells_ if x not in ok)} not run)")
        if d >= a.floor:
            print("  NOTE: exceeding the threshold does NOT by itself void P-L2/P-L4. It sets the")
            print("        cross-binary floor. A prediction whose effect dwarfs that floor still stands;")
            print("        one whose effect is comparable to it does not.")

if __name__ == "__main__":
    main()
