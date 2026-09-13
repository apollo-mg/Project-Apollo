#!/usr/bin/env python3
"""Score PREREG_FLASHNEXT_RESIDENCY.md, Stage 1, from the driver's results.jsonl.

Usage: score_flashnext_residency.py data/receipts/qwen4exp/flashnext_res/results.jsonl
"""
import json, statistics, sys

rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
bw = {r["arm"]: r.get("gbps") for r in rows if r.get("stage") == "bw"}
loads = {r["arm"]: r for r in rows if r.get("stage") == "load"}
done = {r["arm"]: r for r in rows if r.get("stage") == "arm_done"}
req = [r for r in rows if r.get("stage") == "req"]
BASE_0828_TG = 9.0                      # RESULT_FLASHNEXT_PASCAL.md, IQ4_XS -ngl 44, warm decode
THEORY_2CH = 2 * 2133e6 * 8 / 1e9       # two DDR4-2133 channels per socket = 34.13 GB/s


def med(arm, n, key):
    v = [r[key] for r in req if r["arm"] == arm and r["len"] == n and r.get(key)]
    return statistics.median(v) if v else None


def gpu_bufs(arm):
    b = (loads.get(arm) or {}).get("model_buffers_mib") or {}
    return sum(v for k, v in b.items() if k.startswith("CUDA")) or None


def gpu_used(arm):
    """Summed per-GPU memory right after load. Amendment 2: buun's server prints no model-buffer lines at
    the default verbosity, so this is the placement measurement actually available."""
    g = (loads.get(arm) or {}).get("gpu_after_load")
    return sum(g) if g else None


def verdict(ok):
    return "CONFIRMED" if ok else "FALSIFIED"


def missing(*xs):
    return any(x is None for x in xs)


print("## Host bandwidth (STREAM-style triad, best of 10, GB/s)\n")
for a in ("B-L0", "B-L1", "B-R01", "B-IL", "B-FT"):
    print(f"- {a}: {bw.get(a)}")

print("\n## Arms\n")
print("| arm | loaded | GPU MiB after load (per card = sum) | pp 500 / 1800 / 3600 | tg @500 / 1800 / 3600 |")
print("|---|---|---|---|---|")
for a in ("F-Q2", "F-IQ1", "P-Q2", "X-Q2", "P-IQ4", "P-IQ4-numa", "P-IQ4-b"):
    if a not in loads:
        continue
    L = loads[a]
    pp = " / ".join(f"{med(a, n, 'pp_tps'):.1f}" if med(a, n, "pp_tps") else "—" for n in (500, 1800, 3600))
    tg = " / ".join(f"{med(a, n, 'tg_tps'):.2f}" if med(a, n, "tg_tps") else "—" for n in (500, 1800, 3600))
    print(f"| {a} | {L.get('ok')} | {L.get('gpu_after_load')} = {gpu_used(a)} | {pp} | {tg} |")

print("\n## Predictions\n")
F = "F-Q2" if "F-Q2" in done else ("F-IQ1" if "F-IQ1" in done else None)
tag = "" if F == "F-Q2" else " (fallback F-IQ1: cross-quant, labelled as such)"

f_tg, p_tg = (med(F, 500, "tg_tps") if F else None), med("P-Q2", 500, "tg_tps")
print(f"- **P-R1** residency buys decode: " + ("NOT TESTABLE" if missing(f_tg, p_tg) else
      f"{verdict(f_tg / p_tg >= 1.3)} ({F} {f_tg:.2f} vs P-Q2 {p_tg:.2f} tok/s = {f_tg / p_tg:.2f}×){tag}"))

f_pp, p_pp = (med(F, 1800, "pp_tps") if F else None), med("P-Q2", 1800, "pp_tps")
print(f"- **P-R2** residency does NOT buy prefill (<1.5×): " + ("NOT TESTABLE" if missing(f_pp, p_pp) else
      f"{verdict(f_pp / p_pp < 1.5)} ({F} {f_pp:.1f} vs P-Q2 {p_pp:.1f} tok/s = {f_pp / p_pp:.2f}×){tag}"))

a5, a36 = (med(F, 500, "pp_tps"), med(F, 3600, "pp_tps")) if F else (None, None)
print(f"- **P-R3** resident prefill is flat (±20%, 500 → 3600): " + ("NOT TESTABLE" if missing(a5, a36) else
      f"{verdict(abs(a36 / a5 - 1) <= 0.2)} ({a5:.1f} → {a36:.1f} tok/s, {a36 / a5 - 1:+.1%})"))

i4 = med("P-IQ4", 500, "tg_tps")
print(f"- **P-R4** bridge to 08-28 (±15% of {BASE_0828_TG}): " + ("NOT TESTABLE" if i4 is None else
      f"{verdict(abs(i4 / BASE_0828_TG - 1) <= 0.15)} (P-IQ4 {i4:.2f} tok/s, {i4 / BASE_0828_TG - 1:+.1%})"))

n_, a_, b_ = med("P-IQ4-numa", 500, "tg_tps"), med("P-IQ4", 500, "tg_tps"), med("P-IQ4-b", 500, "tg_tps")
if missing(n_, a_, b_):
    print("- **P-R5** --numa distribute: NOT TESTABLE")
else:
    ctrl = (a_ + b_) / 2
    effect, drift = n_ / ctrl - 1, abs(a_ - b_) / ctrl
    v = "INCONCLUSIVE" if drift > abs(effect) else verdict(effect >= 0.03)
    print(f"- **P-R5** --numa distribute ≥ +3%: {v} (numa {n_:.2f} vs control mean {ctrl:.2f}: {effect:+.1%}; "
          f"control drift {drift:.1%})")

gf, gx, basis = gpu_bufs("F-Q2"), gpu_bufs("X-Q2"), "CUDA model buffers"
if missing(gf, gx):   # Amendment 2: the server log carries no buffer lines at the default verbosity
    gf, gx, basis = gpu_used("F-Q2"), gpu_used("X-Q2"), "summed GPU memory after load (Amendment 2)"
print(f"- **P-R6** -ot moves experts (≥2,000 MiB off the GPUs): " + ("NOT TESTABLE" if missing(gf, gx) else
      f"{verdict(gf - gx >= 2000)} (F-Q2 {gf:.0f} vs X-Q2 {gx:.0f} MiB, {basis}: −{gf - gx:.0f})"))

l0, l1, r01, ft = bw.get("B-L0"), bw.get("B-L1"), bw.get("B-R01"), bw.get("B-FT")
if missing(l0, l1):
    print("- **P-BW1**: NOT TESTABLE")
else:
    ok = all(0.5 * THEORY_2CH <= g <= 0.8 * THEORY_2CH for g in (l0, l1))
    print(f"- **P-BW1** local triad in 50–80% of {THEORY_2CH:.1f} GB/s: {verdict(ok)} "
          f"(node 0 {l0:.1f} = {l0 / THEORY_2CH:.0%}, node 1 {l1:.1f} = {l1 / THEORY_2CH:.0%})")
print(f"- **P-BW2** remote ≤ 0.7× local: " + ("NOT TESTABLE" if missing(r01, l0) else
      f"{verdict(r01 <= 0.7 * l0)} (0→1 {r01:.1f} vs local {l0:.1f} = {r01 / l0:.2f}×)"))
print(f"- **P-BW3** both sockets first-touch ≥ 1.7× one socket: " + ("NOT TESTABLE" if missing(ft, l0, l1) else
      f"{verdict(ft >= 1.7 * (l0 + l1) / 2)} ({ft:.1f} vs {(l0 + l1) / 2:.1f} = {ft / ((l0 + l1) / 2):.2f}×)"))

# ---- Stage 2 and Stage 3 (Amendment 3 fixes their scoring rules) ----
print("\n## Stage 2 and Stage 3 arms\n")
print("| arm | loaded | GPU MiB after load | pp 500 / 1800 / 3600 | tg @500 / 1800 / 3600 |")
print("|---|---|---|---|---|")
for a in ("F-X3", "S3-X4", "S3-X4n4", "S3-FIT"):
    if a in loads:
        L = loads[a]
        pp = " / ".join(f"{med(a, n, 'pp_tps'):.1f}" if med(a, n, "pp_tps") else "—" for n in (500, 1800, 3600))
        tg = " / ".join(f"{med(a, n, 'tg_tps'):.2f}" if med(a, n, "tg_tps") else "—" for n in (500, 1800, 3600))
        print(f"| {a} | {L.get('ok')} | {L.get('gpu_after_load')} = {gpu_used(a)} | {pp} | {tg} |")

coh = {r["arm"]: r.get("ok") for r in rows if r.get("stage") == "coherence"}
p_iq4, f_q2_tg, f_q2_pp = med("P-IQ4", 500, "tg_tps"), med("F-Q2", 500, "tg_tps"), med("F-Q2", 1800, "pp_tps")

print("\n## Stage 2 predictions (EXL3 3.05bpw_h5_ng5)\n")
if "F-X3" not in loads:
    print("- **P-X1–P-X5**: NOT RUN")
else:
    L = loads["F-X3"]
    print(f"- **P-X1** loads and answers coherently on sm_60: {verdict(bool(L.get('ok')) and bool(coh.get('F-X3')))}")
    gx3 = gpu_used("F-X3")
    print(f"- **P-X2** all layers resident (-ngl 99 loads, ≥ 40,000 MiB on the cards): " +
          (verdict(bool(L.get('ok')) and (gx3 or 0) >= 40000)) + f" ({gx3} MiB; per-layer count from the -lv 4 reload)")
    x3tg, x3pp = med("F-X3", 500, "tg_tps"), med("F-X3", 1800, "pp_tps")
    print(f"- **P-X3** decode ≥ P-IQ4: " + ("NOT TESTABLE" if missing(x3tg, p_iq4) else
          f"{verdict(x3tg >= p_iq4)} (F-X3 {x3tg:.2f} vs P-IQ4 {p_iq4:.2f} tok/s)"))
    print(f"- **P-X4** decode ≤ F-Q2: " + ("NOT TESTABLE" if missing(x3tg, f_q2_tg) else
          f"{verdict(x3tg <= f_q2_tg)} (F-X3 {x3tg:.2f} vs F-Q2 {f_q2_tg:.2f} tok/s)"))
    print(f"- **P-X5** prefill ≤ 0.75× F-Q2 at 1,800: " + ("NOT TESTABLE" if missing(x3pp, f_q2_pp) else
          f"{verdict(x3pp <= 0.75 * f_q2_pp)} (F-X3 {x3pp:.1f} vs {0.75 * f_q2_pp:.1f}) — name the kernel path before attributing"))

print("\n## Stage 3 predictions (IQ4_XS expert spill, auto-fit retest)\n")
x4arm = "S3-X4" if "S3-X4" in done else ("S3-X4n4" if "S3-X4n4" in done else None)
x4 = med(x4arm, 500, "tg_tps") if x4arm else None
print(f"- **P-S1** S3-X4 loads at -ncmoe 2: " + ("NOT RUN" if "S3-X4" not in loads else verdict(bool(loads["S3-X4"].get("ok")))))
print(f"- **P-S2** expert spill rescues IQ4_XS (≥ 1.4× P-IQ4): " + ("NOT TESTABLE" if missing(x4, p_iq4) else
      f"{verdict(x4 / p_iq4 >= 1.4)} ({x4arm} {x4:.2f} vs P-IQ4 {p_iq4:.2f} = {x4 / p_iq4:.2f}×)"))
print(f"- **P-S3** overhead-bound cost model (> 17.5 tok/s; bandwidth-bound predicts ~15.7): " +
      ("NOT TESTABLE" if x4 is None else f"{verdict(x4 > 17.5)} ({x4arm} {x4:.2f} tok/s)"))
print(f"- **P-S4** -fit on loads on Pascal: " + ("NOT RUN" if "S3-FIT" not in loads else verdict(bool(loads["S3-FIT"].get("ok")))))
fz = med("S3-FIT", 500, "tg_tps")
print(f"- **P-S5** auto-fit spills experts (≥ 1.2× P-IQ4): " + ("NOT TESTABLE" if missing(fz, p_iq4) else
      f"{verdict(fz / p_iq4 >= 1.2)} (S3-FIT {fz:.2f} vs P-IQ4 {p_iq4:.2f} = {fz / p_iq4:.2f}×)"))
