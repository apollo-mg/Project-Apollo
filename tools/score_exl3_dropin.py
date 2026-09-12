#!/usr/bin/env python3
"""Score PREREG_EXL3_DROPIN.md (EXL3 campaign, test 1) mechanically from the driver's results.jsonl.

Usage: score_exl3_dropin.py data/receipts/exl3-campaign/dropin/results.jsonl
"""
import json, statistics, sys

rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]


def of(arm, stage):
    return [r for r in rows if r.get("arm") == arm and r.get("stage") == stage]


def loaded(arm):
    ld = of(arm, "load")
    return bool(ld) and bool(ld[-1].get("ok"))


def t(r, key):
    return (r.get("timings") or {}).get(key)


def decode(arm, stage="greedy"):
    v = [t(r, "predicted_per_second") for r in of(arm, stage)]
    v = [x for x in v if x]
    return statistics.median(v) if len(v) == 3 else None


def acceptance(arm, stage="greedy"):
    rs = of(arm, stage)
    n = sum(int(t(r, "draft_n") or 0) for r in rs)
    a = sum(int(t(r, "draft_n_accepted") or 0) for r in rs)
    return a / n if n else None


def drafted(arm):
    return any(int(t(r, "draft_n") or 0) > 0 for r in of(arm, "greedy") + of(arm, "sampled"))


def engaged(arm):
    rs = of(arm, "greedy") + of(arm, "sampled")
    return len(rs) == 6 and all(int(t(r, "draft_n") or 0) > 0 and int(t(r, "draft_n_accepted") or 0) > 0
                                for r in rs)


def reads_probe(arm):
    v = of(arm, "vision")
    return bool(v) and "kestrel" in (v[-1].get("content") or "").lower()


def prefill(arm):
    v = [r for r in of(arm, "prefill") if r.get("rep") == 2]
    return t(v[0], "prompt_per_second") if v else None


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fmt(x, spec=".2f"):
    return "-" if x is None else format(x, spec)


def verdict(ok):
    return "CONFIRMED" if ok else "FALSIFIED"


def ratio_test(a, b, test, what):
    if a is None or b is None:
        return f"NOT TESTABLE (missing {what})"
    return f"{verdict(test(a / b))} ({a:.2f} / {b:.2f} = {a / b:.3f})"


arms = [a for a in ("X", "X-nomm", "X-novbr", "X-bare", "Xn", "Q", "Qn", "D") if of(a, "load")]
print("| arm | loaded | load s | n_ctx | kv_bpv load / after prefill | VRAM MiB | fact | vision | "
      "greedy t/s | greedy acc | sampled t/s | sampled acc | prefill t/s (tok) |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for a in arms:
    ld = of(a, "load")[-1]
    fact = (of(a, "fact")[-1].get("content") or "").strip()[:24] if of(a, "fact") else "-"
    vis = (of(a, "vision")[-1].get("content") or "").strip()[:24] if of(a, "vision") else "-"
    pf = [r for r in of(a, "prefill") if r.get("rep") == 2]
    after = pf[0].get("kv_bpv_after") if pf else None
    print(f"| {a} | {ld.get('ok')} | {fmt(ld.get('load_s'), '.0f')} | {ld.get('n_ctx', '-')} | "
          f"{ld.get('kv_bpv', '-')} / {after if after is not None else '-'} | {ld.get('gpu_mib', '-')} | "
          f"{fact!r} | {vis!r} | {fmt(decode(a))} | {fmt(acceptance(a), '.3f')} | "
          f"{fmt(decode(a, 'sampled'))} | {fmt(acceptance(a, 'sampled'), '.3f')} | "
          f"{fmt(prefill(a), '.1f')} ({t(pf[0], 'prompt_n') if pf else '-'}) |")
for a in arms:
    for r in of(a, "error") + [r for r in of(a, "load") if not r.get("ok")]:
        print(f"\n{a} {r['stage']}: {r.get('error')}\n  " + "\n  ".join(r.get("tail") or []))

print("\n## Predictions\n")
P = {}
X = loaded("X")
P["P-D1"] = verdict(X)
if not X:
    for k in ("P-D2", "P-D3", "P-D4", "P-D5", "P-D6", "P-D7", "P-D9", "P-D10"):
        P[k] = "NOT TESTABLE (X did not load; see the ladder rows)"
else:
    q_drafts = drafted("Q")
    P["P-D2"] = verdict(engaged("X")) if q_drafts else "VOID (Q never drafted: MTP harness broken)"
    ax, aq = acceptance("X"), acceptance("Q")
    P["P-D3"] = ("VOID (Q never drafted)" if not q_drafts else
                 f"NOT TESTABLE (acceptance X={ax} Q={aq})" if ax is None or aq is None else
                 f"{verdict(abs(ax - aq) <= 0.10)} (X {ax:.3f} vs Q {aq:.3f}, |diff| {abs(ax - aq):.3f})")
    P["P-D4"] = ratio_test(decode("X"), decode("Q"), lambda r: r >= 0.80, "X or Q greedy decode")
    dx, dqn = decode("X"), decode("Qn")
    P["P-D5"] = (f"NOT TESTABLE (X={dx} Qn={dqn})" if dx is None or dqn is None else
                 f"{verdict(dx > dqn)} (X {dx:.2f} vs Qn {dqn:.2f} t/s)")
    P["P-D6"] = verdict(reads_probe("X")) if reads_probe("Q") else "VOID (Q did not read the probe: probe invalid)"
    ld = of("X", "load")[-1]
    bpv = num(ld.get("kv_bpv"))
    P["P-D7"] = f"{verdict(ld.get('n_ctx') == 262144 and bpv is not None and bpv < 16)} " \
                f"(n_ctx {ld.get('n_ctx')}, kv_bpv {ld.get('kv_bpv')})"
    P["P-D9"] = ratio_test(prefill("X"), prefill("Q"), lambda r: r >= 0.70, "X or Q scored prefill")
    P["P-D10"] = ratio_test(decode("X"), decode("Xn"), lambda r: r >= 1.5, "X or Xn greedy decode")
P["P-D8"] = ratio_test(decode("D"), decode("Q"), lambda r: abs(r - 1) <= 0.05, "D or Q greedy decode")
for k in sorted(P, key=lambda k: int(k.split("-D")[1])):
    print(f"- **{k}**: {P[k]}")

print("\n## Headline (descriptive): X vs D at the served sampling\n")
sx, sd = decode("X", "sampled"), decode("D", "sampled")
if sx and sd:
    print(f"X {sx:.2f} t/s (acceptance {fmt(acceptance('X', 'sampled'), '.3f')}) vs "
          f"D {sd:.2f} t/s (acceptance {fmt(acceptance('D', 'sampled'), '.3f')}) = **{sx / sd:.3f}x**")
else:
    print(f"not available (X sampled {sx}, D sampled {sd})")
