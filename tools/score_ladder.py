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
import json, sys, argparse

# Effective parameter count, RECOVERED from the four cells whose bpw the prereg states
# (G-IQ2XS, G-IQ3XXS, B-PTQ1, B-PQ2). It reproduces all four to within 0.02 bpw, so it is
# used to fill in the AD cells the prereg leaves as "?" rather than leaving the size axis
# half-blank. Derived, and labelled as derived wherever it is printed.
NPARAM = 27.21e9

def bpw_of(nbytes):
    return nbytes * 8 / NPARAM if nbytes else None

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
                    help="P-L0 reproducibility floor (measured, not assumed)")
    a = ap.parse_args()
    cells = load(a.results)

    ok  = {k: v for k, v in cells.items() if v.get("status") == "OK"}
    bad = {k: v for k, v in cells.items() if v.get("status") != "OK"}

    print("=" * 96)
    print("LOW-BIT CODEC LADDER -- Qwen3.8-27B, all cells vs the same Q8_0 reference (ref.kld)")
    print("=" * 96)
    print(f"{'cell':<10} {'family':<9} {'GiB':>7} {'bpw':>6} {'mean KLD':>11} {'median':>11} "
          f"{'99% KLD':>10} {'same-top %':>11} {'PPL(Q)':>9}")
    print("-" * 96)
    for k, d in sorted(ok.items(), key=lambda kv: int(kv[1].get("bytes") or 0)):
        fam, bpw = FAMILY.get(k, ("?", None))
        nb = int(d.get("bytes") or 0)
        gib = nb / 2**30
        bpw = bpw_of(nb)          # derived for every cell, so the axis is uniform
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
    gs_cells = [c for c in ok if FAMILY.get(c, ("?",))[0] == "GSQ-RCO"]
    ad_cells = [c for c in ok if FAMILY.get(c, ("?",))[0] == "AD"]
    if not gs_cells or not ad_cells:
        print("  PENDING (need at least one GSQ cell and one AD cell)")
    else:
        pairs = []
        for g in gs_cells:
            for a_ in ad_cells:
                gb, ab = bpw_of(int(ok[g]["bytes"])), bpw_of(int(ok[a_]["bytes"]))
                pairs.append((abs(gb-ab), g, a_, gb, ab))
        pairs.sort()
        print("  cross-family pairs, closest in effective bpw first:")
        for d_, g, a_, gb, ab in pairs:
            gk, ak = kld(g), kld(a_)
            who = "GSQ" if gk < ak else "AD"
            edge = "and GSQ holds FEWER bits" if (gk < ak and gb < ab) else \
                   ("but AD holds MORE bits -- size-confounded" if (ak < gk and ab > gb) else "")
            print(f"    {g:<9}({gb:.2f}bpw, KLD {gk:.6f})  vs  {a_:<9}({ab:.2f}bpw, KLD {ak:.6f})"
                  f"   gap {d_:.2f}bpw  -> {who} lower {edge}")
        d_, g, a_, gb, ab = pairs[0]
        v = "CONFIRMED" if kld(g) < kld(a_) else "FALSIFIED"
        print(f"  nearest pair verdict ({g} vs {a_}): {v}")
        print("  NOTE: AD is systematically FATTER than GSQ at the same quant label")
        print("        (IQ2_XS 2.58 vs 2.91 bpw; IQ3_XXS 3.07 vs 3.55). An AD win at a larger")
        print("        size is not a codec win; a GSQ win at a smaller size is the stronger claim.")

    # ---- P-L4: same-top drops more than KLD implies ----
    print("\nP-L4  Ternary cells drop same-top MORE than their KLD suggests (>=0.5 pp)")
    miss = need("B-PQ2", "G-IQ2XS")
    if miss:
        print(f"  PENDING (missing {', '.join(miss)})")
    else:
        print(f"  B-PQ2  KLD={kld('B-PQ2'):.6f} same-top={top('B-PQ2'):.3f}%")
        print(f"  G-IQ2XS KLD={kld('G-IQ2XS'):.6f} same-top={top('G-IQ2XS'):.3f}%")
        print("  -> needs the KLD-matched comparison described in the prereg; reported, not auto-scored.")

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
        if d < a.floor:
            print(f"  prism={c:.6f}  buun={g:.6f}  |diff|={d:.6e} < floor -> cross-binary comparison VALID")
        else:
            print(f"  prism={c:.6f}  buun={g:.6f}  |diff|={d:.6e} >= floor")
            print("  -> P-L2 and P-L4 are CONFOUNDED by the instrument and must be withdrawn or re-scored.")

if __name__ == "__main__":
    main()
