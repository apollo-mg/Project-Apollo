#!/usr/bin/env python3
"""Score PREREG_FLASHNEXT_BREAK.md (qwen4exp Stage 5) from the shared results.jsonl.

Usage: score_flashnext_break.py ~/flashnext_res/results.jsonl

Committed before the first rung produced a number. Two rules carried from Stage 4, whose headline was
nearly lost to a linear fit returning R² = 0.9907 straight through a real structural break:

  * marginals are computed between ADJACENT rungs, never from a fit;
  * a fitted slope is reported only as a foil, explicitly labelled as the thing not to quote.
"""
import json, math, statistics, sys

# The rungs Stage 4 shares with this ladder, same binary, as {ctx: tok/s} from
# RESULT_FLASHNEXT_SPILL_LADDER.md's "decode 500 / 1800 / 3600" column. Keyed by length deliberately:
# the first committed version of this file held only the ctx-500 value per rung and compared it against
# decode() at its 1800 default, which would have scored a LENGTH MISMATCH as a replication failure.
# Compare like to like at every length, and report the worst deviation.
STAGE4 = {8:  {500: 17.60, 1800: 17.39, 3600: 15.84},
          16: {500: 13.57, 1800: 13.60, 3600: 12.84},
          32: {500: 10.75, 1800: 10.72, 3600: 10.29}}


def load(path):
    runs, done, req = {}, set(), {}
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        a, st = r.get("arm"), r.get("stage")
        if st == "load" and r.get("ok"):
            runs[a] = r
        elif st == "arm_done":
            done.add(a)
            runs.setdefault(a, {}).update({k: r[k] for k in
                                           ("peak_mib", "placement_after_run", "wall_s") if k in r})
        elif st == "req":
            req.setdefault(a, []).append(r)
    return runs, done, req


REPS_EXPECTED = 3


def decode(req, arm, length=1800, partial_ok=False):
    """Median decode tok/s at one context length, or None if the arm has not finished that length.

    Refuses to return a value from fewer than REPS_EXPECTED reps. Rep 0 is systematically 4-10% slow --
    the 64-token warmup never faults in the spilled expert pages -- so a partial arm's median is biased
    low and comparing it against a complete arm invents a deficit. That mistake was made four separate
    times on 2026-09-14 by a reader who knew the rule each time, so the guard is mechanical rather than
    a matter of remembering. Pass partial_ok=True only to display progress, never to compare arms.
    """
    v = [r["tg_tps"] for r in req.get(arm, []) if r.get("len") == length and r.get("tg_tps")]
    if not v or (len(v) < REPS_EXPECTED and not partial_ok):
        return None
    return statistics.median(v)


def peak_sum(runs, arm):
    p = (runs.get(arm) or {}).get("peak_mib")
    return sum(p) if p else None


def imbalance(runs, arm, when="placement_after_run"):
    pl = (runs.get(arm) or {}).get(when) or {}
    return pl.get("imbalance")


def verdict(b):
    return "CONFIRMED" if b else "FALSIFIED"


def main(path):
    runs, done, req = load(path)
    rungs = sorted((int(a.split("-")[1]), a) for a in done if a.startswith("D-"))

    print("## Ladder\n")
    print("| arm | -ncmoe | peak MiB | decode @1800 | imbalance I | anon/file MiB |")
    print("|---|---:|---:|---:|---:|---|")
    for n, a in rungs:
        pl = (runs.get(a) or {}).get("placement_after_run") or {}
        an, fi = pl.get("anon_mib", {}), pl.get("file_mib", {})
        print(f"| {a} | {n} | {peak_sum(runs, a)} | {decode(req, a) or float('nan'):.2f} | "
              f"{imbalance(runs, a)} | {sum(an.values()):.0f} / {sum(fi.values()):.0f} |")

    # ---- marginals between adjacent rungs, in ms per spilled layer ----
    marg = []
    for (n1, a1), (n2, a2) in zip(rungs, rungs[1:]):
        d1, d2 = decode(req, a1), decode(req, a2)
        if not d1 or not d2 or n2 == n1:
            continue
        ms = (1000.0 / d2 - 1000.0 / d1) / (n2 - n1)
        marg.append((n1, n2, ms))
    print("\n## Marginal cost per spilled layer (adjacent rungs only)\n")
    print("| step | ms / layer | implied GB/s |")
    print("|---|---:|---:|")
    for n1, n2, ms in marg:
        print(f"| {n1} → {n2} | {ms:.3f} | {27.6 / ms if ms > 0 else float('nan'):.1f} |")

    print("\n## Predictions\n")

    # P-B7 first: everything else is uninterpretable if the replication fails.
    rep, worst = [], 0.0
    for n, per_len in sorted(STAGE4.items()):
        a = f"D-{n:02d}"
        cells = []
        for L, want in sorted(per_len.items()):
            got = decode(req, a, L)
            if got:
                dev = (got - want) / want
                worst = max(worst, abs(dev))
                cells.append(f"@{L} {got:.2f}/{want:.2f} ({dev * 100:+.1f}%)")
        if cells:
            rep.append(f"{a} " + " ".join(cells))
    if rep:
        ok7 = worst <= 0.05
        print(f"- **P-B7 (replication, read this first)**: {verdict(ok7)} — " + "; ".join(rep) +
              f" — worst deviation {worst * 100:.1f}%")
        if not ok7:
            print("    - **Stage 4's marginals are not reproducible on an identical binary and box.** "
                  "P-B1–P-B3 below are reported but NOT interpretable: a break cannot be distinguished "
                  "from run-to-run variation that exceeds it.")
    else:
        print("- **P-B7**: NOT TESTABLE (no shared rungs completed)")

    # P-B1: regime ratio, stated as a ratio so it survives a build change.
    shallow = [m for a, b, m in marg if b <= 16]
    deep = [m for a, b, m in marg if a >= 20]
    if shallow and deep:
        ratio = statistics.mean(shallow) / statistics.mean(deep)
        print(f"- **P-B1 (two regimes)**: {verdict(ratio >= 1.4)} — shallow mean "
              f"{statistics.mean(shallow):.3f} ms/layer vs deep {statistics.mean(deep):.3f}, "
              f"**ratio {ratio:.2f}×** (band ≥ 1.40)")
    else:
        print("- **P-B1**: NOT TESTABLE (a regime has no steps)")

    # P-B2 / P-B3: where the decline happens, and whether it is a step or a ramp.
    if len(marg) >= 3:
        drops = [(marg[i][2] - marg[i + 1][2], (marg[i + 1][0] + marg[i + 1][1]) / 2, i)
                 for i in range(len(marg) - 1)]
        big, mid, _ = max(drops, key=lambda d: d[0])
        print(f"- **P-B2 (break location)**: {verdict(14 <= mid <= 24)} — largest single drop "
              f"{big:.3f} ms/layer at step midpoint **{mid:g}** (band [14, 24])")
        total = sum(d for d, _, _ in drops if d > 0)
        share = big / total if total > 0 else 0.0
        gradual = sum(1 for d, _, _ in drops if d > 0 and d / total < 0.25) >= 4 if total > 0 else False
        print(f"- **P-B3 (step, not ramp)**: {verdict(share >= 0.5)} — the largest step carries "
              f"**{share * 100:.0f}%** of the total decline (band ≥ 50%)"
              + ("; **≥4 steps each carry <25% — this is a ramp**" if gradual else ""))
        if share < 0.5 and not gradual:
            print("    - neither a clean step nor the prereg's ramp shape: report the marginals, "
                  "do not name a single operating point")
    else:
        print("- **P-B2 / P-B3**: NOT TESTABLE (fewer than three marginals)")

    # P-B4: does placement track depth?
    # Amendment 4: DESCRIPTIVE ONLY. Two runs of rung 16 differed by I = 0.116, larger than the 0.10
    # effect this once predicted across the whole ladder, so one sample per rung cannot carry a verdict.
    # The band is deliberately NOT widened -- loosening after seeing data defeats preregistration.
    i8, i32 = imbalance(runs, "D-08"), imbalance(runs, "D-32")
    allI = [(n, imbalance(runs, a)) for n, a in rungs if imbalance(runs, a) is not None]
    if allI:
        vals = [v for _, v in allI]
        print(f"- **P-B4 (placement vs depth)**: **DESCRIPTIVE, no verdict** (Amendment 4) — I by rung: "
              + ", ".join(f"{n}:{v:.3f}" for n, v in allI))
        print(f"    - range {min(vals):.3f}–{max(vals):.3f}, spread {max(vals) - min(vals):.3f}; "
              f"run-to-run swing at a FIXED rung was 0.116, so a trend smaller than that is not a result")
        if i8 is not None and i32 is not None:
            print(f"    - I(8) {i8:.4f} vs I(32) {i32:.4f}, difference {i8 - i32:+.4f} "
                  f"(what the retired band asked for: ≥ 0.10 — reported, not scored)")
        d = (i8 - i32) if (i8 is not None and i32 is not None) else None
    else:
        d = None
        print("- **P-B4**: NOT TESTABLE (no placement recorded)")

    # P-B5: MiB freed per spilled layer.
    per = []
    for (n1, a1), (n2, a2) in zip(rungs, rungs[1:]):
        v1, v2 = peak_sum(runs, a1), peak_sum(runs, a2)
        if v1 and v2 and n2 != n1:
            per.append((v1 - v2) / (n2 - n1))
    if per:
        mean = statistics.mean(per)
        dev = max(abs(p - mean) / mean for p in per) if mean else 1.0
        print(f"- **P-B5 (MiB/layer constant)**: {verdict(dev <= 0.15)} — mean {mean:.0f} MiB/layer, "
              f"worst deviation {dev * 100:.1f}% (band ±15%)")
    else:
        print("- **P-B5**: NOT TESTABLE")

    # P-B6: the intervention -- gated on placement actually having moved.
    for n in (8, 24):
        ctl, arm = f"D-{n:02d}", f"I-{n:02d}"
        dc, di = decode(req, ctl), decode(req, arm)
        pc, pi = imbalance(runs, ctl), imbalance(runs, arm)
        if dc is None or di is None:
            print(f"- **P-B6 @ {n}**: NOT TESTABLE (arm or control missing)")
            continue
        if pc is None or pi is None or abs(pc - pi) < 0.02:
            print(f"- **P-B6 @ {n}**: **NOT TESTABLE — the intervention was inert.** control I {pc}, "
                  f"interleave I {pi}: placement did not move, so decode "
                  f"{di:.2f} vs {dc:.2f} measures nothing. Not scored as 'no effect'.")
            continue
        gain = (di - dc) / dc
        if n == 8:
            note = "" if d is not None and d >= 0.10 else "  (P-B4 did not confirm — this is exploratory)"
            print(f"- **P-B6 @ 8 (the actionable one)**: {verdict(gain >= 0.05)} — interleave {di:.2f} "
                  f"vs distribute {dc:.2f}, **{gain * 100:+.1f}%** (band ≥ +5%), placement moved "
                  f"{pc:.4f} → {pi:.4f}{note}")
        else:
            print(f"- **P-B6 @ 24 (deep control)**: interleave {di:.2f} vs distribute {dc:.2f}, "
                  f"**{gain * 100:+.1f}%**, placement moved {pc:.4f} → {pi:.4f} — descriptive; "
                  f"a large gain here too would mean the effect is not specific to shallow spill")

    # P-B9 (Amendment 5): the regimes are a capacity effect. Node 0 is 31,772 MiB; host residency is
    # ~1150 MiB per spilled layer, so a rung above ~25 cannot fit on one node and must straddle both.
    i24, i28 = imbalance(runs, "D-24"), imbalance(runs, "D-28")
    if i24 is not None and i28 is not None:
        ok9 = i24 > 0.35 and i28 < 0.35
        print(f"- **P-B9 (capacity boundary)**: {verdict(ok9)} — I(24) {i24:.3f} (want > 0.35), "
              f"I(28) {i28:.3f} (want < 0.35)")
        if ok9:
            print("    - imbalance collapses where host residency stops fitting in one node. Stage 4's "
                  "'spill is cheaper in bulk' is then a placement artifact, not a property of spill, "
                  "and numactl --membind=0 should recover most of the shallow-rung penalty")
    else:
        print("- **P-B9**: NOT TESTABLE (need rungs 24 and 28)")
    print("\n  host residency by rung (fit: ~1150 MiB/layer + 1800):")
    for n, a in rungs:
        pl = (runs.get(a) or {}).get("placement_after_run") or {}
        tot = pl.get("total_mib") or {}
        if tot:
            t = sum(tot.values())
            fits = "fits one node" if t < 30000 else "**exceeds one node**"
            print(f"    - rung {n}: {t:,.0f} MiB, I={pl.get('imbalance')}, {fits}")

    # P-B8: clock elasticity vs spill depth (Amendment 3). 1189 MHz arms are D-/M-; 1063 MHz are C-,
    # plus M-mmap which supplies rung 16 at the low clock. Sensitivity = fractional decode lost to the
    # 10.6% clock cut. Deep spill is host-bound, so it should care less about GPU MHz.
    print("\n## P-B8 — clock elasticity by spill depth (1189 MHz / 250 W vs 1063 MHz / 150 W)\n")
    sens = {}
    for n, lo_arm in ((8, "C-08"), (16, "M-mmap"), (32, "C-32")):
        hi, lo = decode(req, f"D-{n:02d}"), decode(req, lo_arm)
        if hi and lo:
            sens[n] = (hi - lo) / hi
            print(f"- rung **{n}**: {hi:.2f} @1189 vs {lo:.2f} @1063 — **{sens[n] * 100:.1f}%** lost "
                  f"to a 10.6% clock cut (elasticity {sens[n] / 0.106:.2f})")
        else:
            print(f"- rung {n}: NOT TESTABLE (missing {'D-%02d' % n if not hi else lo_arm})")
    if 8 in sens and 32 in sens:
        drop = sens[8] - sens[32]
        print(f"- **P-B8**: {verdict(drop >= 0.03)} — sensitivity {sens[8] * 100:.1f}% at rung 8 vs "
              f"{sens[32] * 100:.1f}% at rung 32, **{drop * 100:+.1f} points** (band ≥ 3.0)")
        if drop >= 0.03:
            print("    - deep-spill configurations can be underclocked for perf-per-watt at a smaller "
                  "throughput cost than shallow ones — a second axis for the efficiency chart")
    else:
        print("- **P-B8**: NOT TESTABLE (need both rungs 8 and 32 at both clocks)")

    # P-B0: the load-mode gate.
    mm, dio = runs.get("M-mmap"), runs.get("M-dio")
    if mm and dio:
        im, idio = imbalance(runs, "M-mmap", "placement_after_load"), imbalance(runs, "M-dio", "placement_after_load")
        dm, dd = decode(req, "M-mmap"), decode(req, "M-dio")
        lm, ld = mm.get("load_s"), dio.get("load_s")
        parts = [f"load {lm}s → {ld}s"]
        if im is not None and idio is not None:
            parts.append(f"I {im:.4f} vs {idio:.4f} (Δ {abs(im - idio):.4f}, band ≤ 0.05)")
        if dm and dd:
            parts.append(f"decode {dm:.2f} vs {dd:.2f} ({(dd - dm) / dm * 100:+.1f}%, band ±3%)")
        ok0 = (im is not None and idio is not None and abs(im - idio) <= 0.05
               and dm and dd and abs(dd - dm) / dm <= 0.03)
        print(f"\n- **P-B0 (load-mode gate)**: {verdict(ok0)} — " + "; ".join(parts))
        if lm and ld:
            engaged = ld < lm * 0.75
            print(f"    - **dio engaged: {engaged}** — functional evidence (load time), not a log string. "
                  f"log hits for 'direct-io': {dio.get('dio_log_hits')}")
            if not engaged:
                print("    - **`-lm dio` parsed but did not speed loading.** Treat DirectIO as NOT in "
                      "effect regardless of what the flag accepted ([[readiness-probes-lie]]).")
    else:
        print("\n- **P-B0**: NOT TESTABLE (5a incomplete)")

    # The foil, reported last and labelled.
    if len(rungs) >= 3:
        xs = [n for n, _ in rungs]
        ys = [1000.0 / decode(req, a) for n, a in rungs if decode(req, a)]
        if len(ys) == len(xs) and len(xs) >= 3:
            mx, my = statistics.mean(xs), statistics.mean(ys)
            sxx = sum((x - mx) ** 2 for x in xs)
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else float("nan")
            pred = [my + slope * (x - mx) for x in xs]
            ss_res = sum((y - p) ** 2 for y, p in zip(ys, pred))
            ss_tot = sum((y - my) ** 2 for y in ys)
            r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
            print(f"\n**The foil — do not quote this.** A single linear fit through all {len(xs)} rungs "
                  f"gives {slope:.3f} ms/layer at R² = {r2:.4f}. Stage 4's R² was 0.9907 across a real "
                  f"1.7× break. **A high R² here is evidence of nothing; read the marginals table.**")


if __name__ == "__main__":
    main(sys.argv[1])
