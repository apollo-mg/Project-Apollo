#!/usr/bin/env python3
"""Score PREREG_EXL3_KLD.md (EXL3 campaign, test 3) mechanically from the driver's results.jsonl.

Usage: score_exl3_kld.py data/receipts/exl3-campaign/kld/results.jsonl
"""
import json, math, sys

rows = {}
for line in open(sys.argv[1]):
    if line.strip():
        r = json.loads(line)
        if r.get("stage") == "run":
            rows[r["arm"]] = r          # the last row per arm wins


def g(arm, key):
    return (rows.get(arm) or {}).get(key)


def vram(arm):
    p = g(arm, "peak_mib")
    return sum(p) if p else None


def fmt(x, spec):
    return "-" if x is None else format(x, spec)


print("| arm | rc | disk GB | peak VRAM MiB | mean KLD ± | median KLD | 99% KLD | same top % ± | PPL(Q) |")
print("|---|---|---|---|---|---|---|---|---|")
for arm in ("REF", "R2", "E", "G4", "G5", "G6"):
    r = rows.get(arm)
    if not r:
        print(f"| {arm} | not run | | | | | | | |")
        continue
    kld = f"{fmt(r.get('kld_mean'), '.6f')} ± {fmt(r.get('kld_err'), '.6f')}" if r.get("kld_mean") is not None else "-"
    top = f"{fmt(r.get('same_top'), '.3f')} ± {fmt(r.get('same_top_err'), '.3f')}" if r.get("same_top") is not None else "-"
    print(f"| {arm} | {r.get('rc')}{' FAILED-DECODE' if r.get('failed_decode') else ''} | "
          f"{fmt(r.get('disk_bytes') and r['disk_bytes'] / 1e9, '.2f')} | {fmt(vram(arm), 'd')} | {kld} | "
          f"{fmt(r.get('kld_median'), '.6f')} | {fmt(r.get('kld_p99'), '.6f')} | {top} | "
          f"{fmt(r.get('ppl_q'), '.4f')} |")


def less(a, b):
    """'a's mean KLD < b's', with the prereg's TIE rule."""
    ka, ea, kb, eb = g(a, "kld_mean"), g(a, "kld_err"), g(b, "kld_mean"), g(b, "kld_err")
    if None in (ka, ea, kb, eb):
        return f"NOT TESTABLE (missing KLD for {a} or {b})"
    vals = f"({a} {ka:.6f} ± {ea:.6f} vs {b} {kb:.6f} ± {eb:.6f})"
    if abs(ka - kb) <= ea + eb:
        return f"TIE {vals}"
    return f"{'CONFIRMED' if ka < kb else 'FALSIFIED'} {vals}"


print("\n## Predictions\n")
r2k, r2t = g("R2", "kld_mean"), g("R2", "same_top")
gate = r2k is not None and r2t is not None and r2k < 1e-4 and r2t >= 99.9
print(f"- **P-K0** (gate): {'CONFIRMED' if gate else 'FALSIFIED'} (R2 mean KLD {r2k}, same top {r2t})")
if not gate:
    for k in ("P-K1", "P-K2", "P-K3", "P-K4"):
        print(f"- **{k}**: VOID (the reference is not reproducible, or R2 did not run)")
else:
    print(f"- **P-K1**: {less('E', 'G5')}")
    print(f"- **P-K2**: {less('E', 'G4')}")
    print(f"- **P-K3**: {less('G6', 'E')}")
    et = g("E", "same_top")
    print(f"- **P-K4**: " + ("NOT TESTABLE (no same-top for E)" if et is None else
                             f"{'CONFIRMED' if et >= 95.0 else 'FALSIFIED'} (E same top {et:.3f}%)"))

print("\n## Headline (descriptive): EXL3 against the GGUF size curve, by peak VRAM\n")
ev, ek = vram("E"), g("E", "kld_mean")
pts = sorted((vram(a), g(a, "kld_mean"), a) for a in ("G4", "G5", "G6")
             if vram(a) is not None and g(a, "kld_mean") is not None)
if ev is None or ek is None or not pts:
    print("not available")
else:
    lo = [p for p in pts if p[0] <= ev]
    hi = [p for p in pts if p[0] >= ev]
    if lo and hi:
        a, b = lo[-1], hi[0]
        t = 0.0 if b[0] == a[0] else (ev - a[0]) / (b[0] - a[0])
        interp = math.exp(math.log(a[1]) + t * (math.log(b[1]) - math.log(a[1])))
        print(f"EXL3 at {ev} MiB: mean KLD {ek:.6f} vs the curve's {interp:.6f} "
              f"(interpolated between {a[2]} at {a[0]} MiB and {b[2]} at {b[0]} MiB) -> "
              f"**{'BELOW' if ek < interp else 'ABOVE'} the GGUF curve**, ratio {ek / interp:.3f}")
    else:
        print(f"EXL3 at {ev} MiB is not bracketed by the GGUF arms {[(p[2], p[0]) for p in pts]}")
    for v, k, a in pts:
        rel = ("dominates" if (ek < k and ev <= v) else "is dominated by" if (ek > k and ev >= v)
               else "trades off against")
        print(f"- EXL3 {rel} {a} ({a}: {v} MiB, KLD {k:.6f})")
