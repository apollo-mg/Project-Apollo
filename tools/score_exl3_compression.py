#!/usr/bin/env python3
"""Score PREREG_EXL3_COMPRESSION.md (EXL3 campaign, test 10) from the shared KLD results.jsonl.

Usage: score_exl3_compression.py data/receipts/exl3-campaign/kld/results.jsonl
"""
import json, math, sys

EXL3 = {"E25": "EXL3 2.50bpw", "E30": "EXL3 3.00bpw", "E35": "EXL3 3.50bpw",
        "E": "EXL3 4.00bpw", "E5": "EXL3 5.00bpw"}
GGUF = {"G2x": "AD-IQ2_XS", "G3xx": "AD-IQ3_XXS", "G3m": "i1-IQ3_M",
        "G4": "UD-IQ4_XS", "G5": "UD-Q4_K_M", "G6": "Q6_K"}

rows = {}
for line in open(sys.argv[1]):
    if line.strip():
        r = json.loads(line)
        if r.get("stage") == "run" and r.get("rc") == 0 and r.get("kld_mean") is not None:
            rows[r["arm"]] = r        # last successful row per arm wins


def vram(a):
    p = (rows.get(a) or {}).get("peak_mib")
    return sum(p) if p else None


def kld(a):
    return (rows.get(a) or {}).get("kld_mean")


def err(a):
    return (rows.get(a) or {}).get("kld_err") or 0.0


def curve(names):
    pts = [(vram(a), kld(a), a) for a in names if vram(a) and kld(a)]
    return sorted(pts)


def interp(pts, v):
    """log-linear interpolation of KLD at VRAM v; None if v is outside the measured range."""
    lo = [p for p in pts if p[0] <= v]
    hi = [p for p in pts if p[0] >= v]
    if not lo or not hi:
        return None
    a, b = lo[-1], hi[0]
    if a[0] == b[0]:
        return a[1]
    t = (v - a[0]) / (b[0] - a[0])
    return math.exp(math.log(a[1]) + t * (math.log(b[1]) - math.log(a[1])))


def inverse(pts, target):
    """VRAM at which the curve reaches `target` KLD, by the same interpolation; None if unreachable."""
    for (v1, k1, _), (v2, k2, _) in zip(pts, pts[1:]):
        if (k1 >= target >= k2) or (k2 >= target >= k1):
            if k1 == k2:
                return v1
            t = (math.log(target) - math.log(k1)) / (math.log(k2) - math.log(k1))
            return v1 + t * (v2 - v1)
    return None


def verdict(b):
    return "CONFIRMED" if b else "FALSIFIED"


print("| arm | model | peak VRAM MiB | mean KLD ± | median | same top % |")
print("|---|---|---|---|---|---|")
for group in (EXL3, GGUF):
    for a, name in group.items():
        if a in rows:
            r = rows[a]
            print(f"| {a} | {name} | {vram(a)} | {kld(a):.6f} ± {err(a):.6f} | "
                  f"{r.get('kld_median', float('nan')):.6f} | {r.get('same_top', float('nan')):.3f} |")

E, G = curve(EXL3), curve(GGUF)
print("\n## Predictions\n")

b, e30 = rows.get("BRIDGE"), rows.get("E30")
if b and e30:
    d = abs(b["kld_mean"] - e30["kld_mean"])
    tol = (b.get("kld_err") or 0) + (e30.get("kld_err") or 0)
    print(f"- **P-C0** (bridge): {verdict(d <= tol)} (da458765d {b['kld_mean']:.6f} vs 9ae8f0f40 "
          f"{e30['kld_mean']:.6f}, |diff| {d:.6f} vs tolerance {tol:.6f})")
else:
    print("- **P-C0** (bridge): NOT RUN")

checks = []
for v, k, a in E:
    gi = interp(G, v)
    if gi:
        checks.append((a, v, k, gi, k < gi))
print(f"- **P-C1**: " + (verdict(all(c[4] for c in checks)) if checks else "NOT TESTABLE") +
      " (" + "; ".join(f"{a} {k:.5f} vs GGUF {gi:.5f} at {v} MiB" for a, v, k, gi, _ in checks) + ")")

if len(checks) >= 2:
    small, large = checks[0], checks[-1]
    gap_s = math.log(small[3]) - math.log(small[2])
    gap_l = math.log(large[3]) - math.log(large[2])
    print(f"- **P-C2**: {verdict(gap_s > gap_l)} (log-gap {gap_s:.3f} at {small[1]} MiB vs {gap_l:.3f} at {large[1]} MiB)")
else:
    print("- **P-C2**: NOT TESTABLE")


def pair(a, b_, label):
    ka, kb = kld(a), kld(b_)
    if ka is None or kb is None:
        return f"- **{label}**: NOT TESTABLE ({a} or {b_} missing)"
    tol = err(a) + err(b_)
    if abs(ka - kb) <= tol:
        return f"- **{label}**: TIE ({a} {ka:.6f} vs {b_} {kb:.6f}, within {tol:.6f})"
    return (f"- **{label}**: {verdict(ka < kb)} ({a} {ka:.6f} at {vram(a)} MiB vs "
            f"{b_} {kb:.6f} at {vram(b_)} MiB)")


print(pair("E25", "G2x", "P-C3"))
print(pair("E30", "G3xx", "P-C4"))

print("\n## The compression exchange rate: VRAM a GGUF needs to match each EXL3 point\n")
for v, k, a in E:
    need = inverse(G, k)
    if need:
        print(f"- **{EXL3[a]}** reaches KLD {k:.6f} at **{v} MiB**; a GGUF needs **{need:.0f} MiB** "
              f"for the same fidelity — **{need - v:+.0f} MiB ({(need / v - 1) * 100:+.1f}%)**")
    else:
        print(f"- **{EXL3[a]}**: KLD {k:.6f} at {v} MiB — outside the GGUF curve's measured range")
