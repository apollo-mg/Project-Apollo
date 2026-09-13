#!/usr/bin/env python3
"""Score PREREG_EXL3_USABLE.md (EXL3 campaign, test 11) from the two HumanEval+ result files.

Usage: score_exl3_usable.py <dir with usable_results_exl3.json and usable_results_gguf.json>

The pair (Amendment 2): EXL3 3.00bpw at 10,568 MiB against unsloth UD-IQ3_XXS rev f9758630 at 11,532 MiB —
a distribution tie in test 10 (KLD 0.046152 vs 0.047609, inside the summed uncertainties) with EXL3 964 MiB
smaller. K=1 at temperature 0, thinking off (Amendments 1 and 3), so pass@1 is an existence proof per problem
and is reported as "solved n of 164 greedy", never as a deployment rate.
"""
import json, math, os, sys

ARMS = ("exl3", "gguf")
LABEL = {"exl3": "EXL3 3.00bpw (10,568 MiB)", "gguf": "UD-IQ3_XXS @ f9758630 (11,532 MiB)"}
SUBSTANTIAL = 5.0     # percentage points; Mark's bar, fixed before the data
DEGEN = ("TRUNCATED", "NO_ANSWER")


def load(d, arm):
    p = os.path.join(d, f"usable_results_{arm}.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p))


def two_sided_sign_p(a, b):
    """Exact two-sided binomial test on the discordant pairs (n=a+b, p=0.5)."""
    n = a + b
    if n == 0:
        return 1.0
    k = min(a, b)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def verdict(ok):
    return "CONFIRMED" if ok else "FALSIFIED"


d = sys.argv[1] if len(sys.argv) > 1 else "."
data = {a: load(d, a) for a in ARMS}
missing = [a for a in ARMS if data[a] is None]
if missing:
    print(f"NOT RUN: missing results for {', '.join(missing)}")
    sys.exit(0)

per = {}
for a in ARMS:
    r = data[a]
    per[a] = {t["task_id"]: bool(t["passes"][0]) for t in r["results"]}
    tally = r.get("sample_tally", {})
    toks = [n for t in r["results"] for n in t.get("out_toks", [])]
    print(f"### {LABEL[a]}")
    print(f"- solved **{sum(per[a].values())} of {len(per[a])}** greedy  ({r.get('pooled_pass@1', 0) * 100:.1f}%)")
    print(f"- buckets: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    print(f"- mean output tokens: {sum(toks) / len(toks):.0f}" if toks else "- mean output tokens: n/a")
    print(f"- thinking fired on {sum(1 for t in r['results'] for c in t.get('rc_chars', []) if c > 0)} samples "
          f"(expected 0: thinking is off)\n")

common = sorted(set(per["exl3"]) & set(per["gguf"]), key=lambda t: int(t.split("/")[1]))
if len(common) < max(len(per[a]) for a in ARMS):
    print(f"**Scored over the {len(common)} problems both arms completed** (Amendment 1's partial-run rule).\n")

e_only = [t for t in common if per["exl3"][t] and not per["gguf"][t]]
g_only = [t for t in common if per["gguf"][t] and not per["exl3"][t]]
e_rate = 100 * sum(per["exl3"][t] for t in common) / len(common)
g_rate = 100 * sum(per["gguf"][t] for t in common) / len(common)
p = two_sided_sign_p(len(e_only), len(g_only))
delta = e_rate - g_rate

print("## Paired comparison\n")
print(f"- EXL3 {e_rate:.1f}% vs GGUF {g_rate:.1f}% over {len(common)} paired problems — **{delta:+.1f} points**")
print(f"- discordant: EXL3 only **{len(e_only)}**, GGUF only **{len(g_only)}**, tied {len(common) - len(e_only) - len(g_only)}")
print(f"- two-sided sign test **p = {p:.3f}**")
if e_only:
    print(f"- EXL3-only: {', '.join(e_only[:12])}{' …' if len(e_only) > 12 else ''}")
if g_only:
    print(f"- GGUF-only: {', '.join(g_only[:12])}{' …' if len(g_only) > 12 else ''}")

print("\n## Predictions\n")
if p >= 0.05:
    print(f"- **P-U1** EXL3's pass@1 exceeds the GGUF's: **NO DETECTABLE DIFFERENCE** "
          f"({delta:+.1f} points, p = {p:.3f} ≥ 0.05) — the prereg's rule: report a difference only at p < 0.05")
else:
    print(f"- **P-U1** EXL3's pass@1 exceeds the GGUF's: {verdict(delta > 0)} ({delta:+.1f} points, p = {p:.3f})")
print(f"- **P-U2** the difference is substantial (≥ {SUBSTANTIAL:.0f} points): {verdict(delta >= SUBSTANTIAL)} "
      f"({delta:+.1f} points)" + ("" if p < 0.05 else " — and not detectable at all, see P-U1"))

deg = {a: sum(data[a].get("sample_tally", {}).get(k, 0) for k in DEGEN) for a in ARMS}
tok = {a: (lambda v: sum(v) / len(v) if v else float("nan"))([n for t in data[a]["results"] for n in t.get("out_toks", [])])
       for a in ARMS}
print(f"- **P-U3** EXL3 produces fewer degenerate outputs (Amendment 4: {'+'.join(DEGEN)} buckets, with mean "
      f"output tokens alongside): {verdict(deg['exl3'] < deg['gguf'])} "
      f"(EXL3 {deg['exl3']} vs GGUF {deg['gguf']}; mean tokens {tok['exl3']:.0f} vs {tok['gguf']:.0f})")
print(f"- **P-U4** both arms clear 50%: {verdict(e_rate >= 50 and g_rate >= 50)} "
      f"(EXL3 {e_rate:.1f}%, GGUF {g_rate:.1f}%)")

print("\n*K=1 at temperature 0: each figure is 'solved this problem greedily', not a deployment rate. "
      "Wall-clock is not comparable — the arms ran side by side (Amendment 3).*")
